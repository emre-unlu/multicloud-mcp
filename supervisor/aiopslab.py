"""Helpers for interacting with the AIOpsLab service.

This module provides a thin wrapper around the public FastAPI endpoints
exposed by https://github.com/microsoft/AIOpsLab. It makes it easy to:

* Discover which fault-injection problems are available.
* Inspect which built-in agents the service exposes.
* Trigger a simulation that initializes a problem (injecting the fault)
  so you can point the diagnostics tooling at the impacted cluster.

The module can be used as a library or a small CLI::

    python -m supervisor.aiopslab --service-url http://localhost:1818 --list-problems
    python -m supervisor.aiopslab --service-url http://localhost:1818 \
        --problem-id k8s_target_port-misconfig-mitigation-1 --max-steps 0

When `--max-steps` is set to 0 the orchestrator will initialize the
problem (which applies the intended error) without letting the default
agent attempt a fix. This is useful when you just want to validate
diagnostics against a known-faulty environment.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

import requests


class AIOpsLabClient:
    """Minimal client for the AIOpsLab FastAPI service."""

    def __init__(self, base_url: str) -> None:
        clean = base_url.rstrip("/")
        if not clean.startswith("http://") and not clean.startswith("https://"):
            raise ValueError("service url must start with http:// or https://")
        self.base_url = clean

    def list_problems(self) -> List[str]:
        """Return the problem identifiers that can be simulated."""
        resp = requests.get(f"{self.base_url}/problems", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response payload for /problems")
        return [str(item) for item in data]

    def list_agents(self) -> List[str]:
        """Return the registered agent identifiers."""
        resp = requests.get(f"{self.base_url}/agents", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response payload for /agents")
        return [str(item) for item in data]

    def simulate(
        self,
        *,
        problem_id: str,
        agent_name: str,
        max_steps: int = 10,
        model: Optional[str] = None,
        repetition_penalty: Optional[float] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Trigger a simulation and return the decoded JSON payload."""

        payload: Dict[str, Any] = {
            "problem_id": problem_id,
            "agent_name": agent_name,
            "max_steps": max_steps,
        }
        if model is not None:
            payload["model"] = model
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = requests.post(
            f"{self.base_url}/simulate", headers={"Content-Type": "application/json"}, json=payload, timeout=120
        )
        resp.raise_for_status()
        return resp.json()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with an AIOpsLab service instance.")
    parser.add_argument(
        "--service-url",
        default="http://127.0.0.1:1818",
        help="Base URL for the AIOpsLab FastAPI service (default: http://127.0.0.1:1818)",
    )
    parser.add_argument("--list-problems", action="store_true", help="List available problem IDs and exit")
    parser.add_argument("--list-agents", action="store_true", help="List available agent IDs and exit")
    parser.add_argument("--problem-id", help="Problem identifier to simulate (see --list-problems)")
    parser.add_argument(
        "--agent-name",
        default="gpt",
        help="Agent identifier to use for /simulate (see --list-agents). Default: gpt",
    )
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum steps to allow the agent to run")
    parser.add_argument("--model", help="Model name for vLLM agent")
    parser.add_argument("--repetition-penalty", type=float, help="Repetition penalty for vLLM agent")
    parser.add_argument("--temperature", type=float, help="Sampling temperature for vLLM agent")
    parser.add_argument("--top-p", type=float, help="Top-p for vLLM agent")
    parser.add_argument("--max-tokens", type=int, help="Max tokens for vLLM agent")
    return parser


def _format_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    client = AIOpsLabClient(args.service_url)

    if args.list_problems:
        problems = client.list_problems()
        print("Available problems:")
        for prob in sorted(problems):
            print(f"- {prob}")
        return 0

    if args.list_agents:
        agents = client.list_agents()
        print("Available agents:")
        for agent in sorted(agents):
            print(f"- {agent}")
        return 0

    if not args.problem_id:
        parser.error("--problem-id is required unless listing problems/agents")

    response = client.simulate(
        problem_id=args.problem_id,
        agent_name=args.agent_name,
        max_steps=args.max_steps,
        model=args.model,
        repetition_penalty=args.repetition_penalty,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
    )
    print(_format_json(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
