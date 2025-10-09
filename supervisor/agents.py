# supervisor/agents.py
import os, json, requests
from typing import Any, Dict
from langchain.tools import BaseTool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

def _make_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("MODEL", "openai:gpt-4o-mini")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not model.startswith("openai:"):
        raise RuntimeError("MODEL must start with 'openai:' (e.g., openai:gpt-4o-mini)")
    return ChatOpenAI(model=model.split(":", 1)[1], temperature=0)

HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

def _post_mcp(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(url, headers=HDRS, data=json.dumps(payload), timeout=90, stream=True)
    r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            return json.loads(line[6:])
    raise RuntimeError("No 'data:' event found in MCP response (SSE)")

def mcp_call_tool(server_url: str, name: str, arguments: Dict[str, Any]) -> Any:
    payload = {"jsonrpc":"2.0","id":"x","method":"tools/call","params":{"name":name,"arguments":arguments}}
    resp = _post_mcp(server_url, payload)
    result = (resp or {}).get("result") or {}
    if "structuredContent" in result and result["structuredContent"] is not None:
        return result["structuredContent"]
    content = result.get("content") or []
    for c in content:
        if c.get("type") == "text":
            return c.get("text")
    return result

K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080")
ALLOWED = {"list_namespaces","list_pods","pod_logs","create_deployment","scale_deployment"}

class MCPTool(BaseTool):
    name: str
    description: str
    tool_name_on_worker: str

    def _run(self, *args, **kwargs) -> str:
        if self.tool_name_on_worker not in ALLOWED:
            return f"Tool {self.tool_name_on_worker} not allowed"
        out = mcp_call_tool(K8S_MCP_URL, self.tool_name_on_worker, kwargs or {})
        return json.dumps(out, ensure_ascii=False)

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError

def build_agent() -> AgentExecutor:
    tools = [
        MCPTool(name="k8s_list_namespaces", description="List Kubernetes namespaces.", tool_name_on_worker="list_namespaces"),
        MCPTool(name="k8s_list_pods", description="List pod names in a namespace. Args: namespace:str", tool_name_on_worker="list_pods"),
        MCPTool(name="k8s_pod_logs", description="Get recent pod logs. Args: namespace:str, pod:str, tail_lines:int=80", tool_name_on_worker="pod_logs"),
        MCPTool(name="k8s_create_deployment", description="Create a small deployment. Args: namespace:str, name:str, image:str='nginx', replicas:int", tool_name_on_worker="create_deployment"),
        MCPTool(name="k8s_scale_deployment", description="Scale a deployment. Args: namespace:str, name:str, replicas:int", tool_name_on_worker="scale_deployment"),
    ]

    SYSTEM = """You are the Supervisor agent. Plan briefly, then call tools.
- Prefer read/list actions first.
- Never delete/terminate resources.
- When creating/scaling, always specify namespace and replica count.
- If user is ambiguous, ask one short clarifying question.
- Output concise results.
"""

    # REQUIRED by create_openai_tools_agent: MessagesPlaceholder("agent_scratchpad")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    llm = _make_llm()
    import os, sys
    print(
        "[supervisor] Using OpenAI model:",
        os.getenv("MODEL"),
        "BASE_URL=",
        os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "<default>",
        file=sys.stderr,
    )
    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)
