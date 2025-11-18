"""Tooling and agent wiring for the Supervisor service."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional

import requests
from langchain.agents import create_agent
from langchain.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import HumanInTheLoopMiddleware

try:
    from langchain.tools import StructuredTool
except ImportError:  
    StructuredTool = None
try:
    from langchain_ollama import ChatOllama
except ImportError:  
    ChatOllama = None

K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080")
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
_SESSION = requests.Session()
CHECKPOINTER = InMemorySaver()
HITL_POLICY: Dict[str, Any] = {
    "k8s_create_deployment": True,
    "k8s_scale_deployment": True,
    "k8s_delete_deployment": True,
    "k8s_delete_pod": True,
    "k8s_list_namespaces": False,
    "k8s_list_pods": False,
    "k8s_pod_logs": False,
    "k8s_diagnose_cluster": {"allowed_decisions": ["approve", "reject"]},
    "k8s_get_namespace": {"allowed_decisions": ["approve", "reject", "edit"]},
}


def _post_mcp(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a JSON-RPC request to the MCP server and return the decoded line."""
    response = _SESSION.post(url, headers=HDRS, json=payload, timeout=90, stream=True)
    response.raise_for_status()
    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            return json.loads(line[6:])
    raise RuntimeError("No 'data:' line from MCP")


def mcp_call_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """Invoke a named MCP tool and return its structured payload."""
    resp = _post_mcp(
        K8S_MCP_URL,
        {
            "jsonrpc": "2.0",
            "id": "supervisor",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    result = (resp or {}).get("result") or {}
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    for chunk in result.get("content") or []:
        if chunk.get("type") == "text":
            return chunk.get("text")
    return result


def _call_mcp_json(tool_name: str, **arguments: Any) -> str:
    """Convenience wrapper returning a JSON string to keep LangChain outputs uniform."""
    clean_args = {k: v for k, v in arguments.items() if v is not None}
    data = mcp_call_tool(tool_name, clean_args)
    # Keep compact to make responses easier to read in UI.
    return json.dumps(data, indent=2, ensure_ascii=False)


def _build_tools() -> Iterable[BaseTool]:
    """Construct LangChain tools that proxy to MCP endpoints."""

    def wrap(fn, *, name: str, description: str) -> BaseTool:
        if StructuredTool is not None:
            return StructuredTool.from_function(fn, name=name, description=description)
        # Fallback to classic tool decorator which returns a Tool instance.
        decorated = tool(fn, return_direct=False)
        decorated.name = name
        decorated.description = description
        return decorated

    def list_namespaces() -> str:
        """List Kubernetes namespaces."""
        return _call_mcp_json("list_namespaces")

    def list_pods(namespace: str) -> str:
        """List pod names in a namespace."""
        return _call_mcp_json("list_pods", namespace=namespace)

    def pod_logs(namespace: str, pod: str, tail_lines: int = 80) -> str:
        """Get recent pod logs."""
        return _call_mcp_json("pod_logs", namespace=namespace, pod=pod, tail_lines=tail_lines)

    def create_deployment(namespace: str, name: str, image: str = "nginx", replicas: int = 1) -> str:
        """Create a small deployment."""
        return _call_mcp_json(
            "create_deployment",
            namespace=namespace,
            name=name,
            image=image,
            replicas=replicas,
        )

    def scale_deployment(namespace: str, name: str, replicas: int) -> str:
        """Scale an existing deployment."""
        return _call_mcp_json(
            "scale_deployment",
            namespace=namespace,
            name=name,
            replicas=replicas,
        )

    def delete_deployment(namespace: str, name: str, grace_period_seconds: Optional[int] = None) -> str:
        """Delete a deployment after confirming namespace/name."""
        return _call_mcp_json(
            "delete_deployment",
            namespace=namespace,
            name=name,
            grace_period_seconds=grace_period_seconds,
        )

    def delete_pod(namespace: str, name: str, grace_period_seconds: Optional[int] = None) -> str:
        """Delete a pod and scale the owning deployment down when applicable."""
        return _call_mcp_json(
            "delete_pod",
            namespace=namespace,
            name=name,
            grace_period_seconds=grace_period_seconds,
        )

    def diagnose_cluster(namespace: Optional[str] = None, include_metrics: bool = False) -> str:
        """Summarize cluster health, optionally focusing on a namespace and metrics."""
        return _call_mcp_json(
            "diagnose_cluster",
            namespace=namespace,
            include_metrics=include_metrics,
        )

    return [
        wrap(
            list_namespaces,
            name="k8s_list_namespaces",
            description=list_namespaces.__doc__ or "",
        ),
        wrap(
            list_pods,
            name="k8s_list_pods",
            description=list_pods.__doc__ or "",
        ),
        wrap(
            pod_logs,
            name="k8s_pod_logs",
            description=pod_logs.__doc__ or "",
        ),
        wrap(
            create_deployment,
            name="k8s_create_deployment",
            description=create_deployment.__doc__ or "",
        ),
        wrap(
            scale_deployment,
            name="k8s_scale_deployment",
            description=scale_deployment.__doc__ or "",
        ),
        wrap(
            delete_deployment,
            name="k8s_delete_deployment",
            description=delete_deployment.__doc__ or "",
        ),
        wrap(
            delete_pod,
            name="k8s_delete_pod",
            description=delete_pod.__doc__ or "",
        ),
        wrap(
            diagnose_cluster,
            name="k8s_diagnose_cluster",
            description=diagnose_cluster.__doc__ or "",
        ),
    ]


SYSTEM_PROMPT = """You are the Supervisor agent. Plan briefly, then call tools.
- Prefer read/list actions first.
- Only delete resources after explicit human approval.
- When creating/scaling, always specify namespace and replica count.
- Use diagnostics to gather cluster health before risky operations.
- If ambiguous, ask ONE short clarifying question.
- Output concise results."""


def build_agent_v1() -> Any:
    """Create the LangChain agent wired up with MCP-backed tools."""
    model_spec = os.getenv("MODEL", "ollama:gpt-oss:20b")
    tools = list(_build_tools())
    llm = model_spec
    if model_spec.startswith("ollama:"):
        if ChatOllama is None:
            raise RuntimeError(
                "MODEL is set to an Ollama backend but langchain_ollama is not installed. "
                "Install with `pip install langchain-ollama`."
            )
        _, _, remaining = model_spec.partition(":")
        model_name = remaining or "ollama:gpt-oss:20b"
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        llm = ChatOllama(model=model_name, base_url=base_url)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on=HITL_POLICY,
                description_prefix="Tool execution pending approval",
            )
        ],
        checkpointer=CHECKPOINTER,
    )
