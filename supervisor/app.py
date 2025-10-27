# supervisor/app.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from langchain.messages import HumanMessage, AIMessage
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
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/run")
def run(req: RunReq):
    agent = get_agent()
    result = agent.invoke({
        "messages": [
            {"role": "user", "content": req.goal}
        ]
    })
    # result is usually a dict with "messages" (LangChain v1)
    messages = result.get("messages", [])
    # take the last AI message
    last_text = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) or (isinstance(m, dict) and m.get("role") == "assistant"):
            last_text = m.get("content") if isinstance(m, dict) else m.content
            break
    return {"ok": True, "answer": last_text or "(no final answer)"}
