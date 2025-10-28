"""FastAPI surface for the Supervisor agent."""

from __future__ import annotations

from fastapi import FastAPI
from langchain.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from .agents import build_agent_v1

app = FastAPI()
_agent = None


class RunReq(BaseModel):
    goal: str


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent_v1()
    return _agent


@app.get("/health")
def health():
    try:
        get_agent()
    except Exception as exc:  # pragma: no cover - surfaced via API
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


@app.post("/run")
def run(req: RunReq):
    agent = get_agent()
    result = agent.invoke({"messages": [HumanMessage(content=req.goal)]})

    # `create_agent` returns a dict containing `output` and `messages`.
    answer = result.get("output")
    if not answer:
        messages = result.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                answer = message.content
                break
            if isinstance(message, dict) and message.get("role") == "assistant":
                answer = message.get("content")
                break

    return {"ok": True, "answer": answer or "(no final answer)"}
