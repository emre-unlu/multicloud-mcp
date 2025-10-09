# supervisor/app.py
import traceback
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from .agents import build_agent

load_dotenv()
app = FastAPI(title="Supervisor (LangChain)")

_agent = None
_agent_error = None

def get_agent():
    global _agent, _agent_error
    if _agent or _agent_error:
        return _agent
    try:
        _agent = build_agent()
    except Exception as e:
        _agent_error = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    if _agent is None and _agent_error is None:
        _agent_error = "build_agent() returned None without raising"
    return _agent

class RunIn(BaseModel):
    goal: str

class RunOut(BaseModel):
    answer: str

@app.get("/health")
def health():
    ag = get_agent()
    return {"ok": ag is not None, "error": _agent_error}

@app.post("/run", response_model=RunOut)
def run(req: RunIn):
    ag = get_agent()
    if ag is None:
        return RunOut(answer=f"Agent failed to initialize: {_agent_error}")
    try:
        # No agent_scratchpad here
        res = ag.invoke({"input": req.goal})
        return RunOut(answer=res.get("output", str(res)))
    except Exception as e:
        traceback.print_exc()
        return RunOut(answer=f"Error: {type(e).__name__}: {e}")
