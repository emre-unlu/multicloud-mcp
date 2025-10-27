# supervisor/agents.py
import os, json, requests
from typing import Any, Dict
from langchain.tools import BaseTool
from langchain.agents import create_agent          
from langchain.tools import tool                   
from langchain.messages import AIMessage          
from langchain_ollama import ChatOllama

K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080")
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

def _post_mcp(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(url, headers=HDRS, json=payload, timeout=90, stream=True)
    r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            return json.loads(line[6:])
    raise RuntimeError("No 'data:' line from MCP")

def mcp_call_tool(name: str, arguments: Dict[str, Any]) -> Any:
    resp = _post_mcp(
        K8S_MCP_URL,
        {"jsonrpc": "2.0", "id": "x", "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
    )
    result = (resp or {}).get("result") or {}
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    for c in result.get("content") or []:
        if c.get("type") == "text":
            return c.get("text")
    return result


K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080")
ALLOWED = {"list_namespaces","list_pods","pod_logs","create_deployment","scale_deployment"}

@tool("k8s_list_namespaces")
def k8s_list_namespaces() -> str:
    """List Kubernetes namespaces."""
    out = mcp_call_tool("list_namespaces", {})
    return json.dumps(out)

@tool("k8s_list_pods")
def k8s_list_pods(namespace: str) -> str:
    """List pod names in a namespace. Args: namespace:str"""
    out = mcp_call_tool("list_pods", {"namespace": namespace})
    return json.dumps(out)

@tool("k8s_pod_logs")
def k8s_pod_logs(namespace: str, pod: str, tail_lines: int = 80) -> str:
    """Get recent pod logs. Args: namespace:str, pod:str, tail_lines:int=80"""
    out = mcp_call_tool("pod_logs", {"namespace": namespace, "pod": pod, "tail_lines": tail_lines})
    return json.dumps(out)

@tool("k8s_create_deployment")
def k8s_create_deployment(namespace: str, name: str, image: str = "nginx", replicas: int = 1) -> str:
    """Create a small deployment. Args: namespace, name, image='nginx', replicas:int(1..5)"""
    out = mcp_call_tool("create_deployment", {
        "namespace": namespace, "name": name, "image": image, "replicas": replicas
    })
    return json.dumps(out)

@tool("k8s_scale_deployment")
def k8s_scale_deployment(namespace: str, name: str, replicas: int) -> str:
    """Scale a deployment. Args: namespace, name, replicas:int(1..5)"""
    out = mcp_call_tool("scale_deployment", {
        "namespace": namespace, "name": name, "replicas": replicas
    })
    return json.dumps(out)

SYSTEM = """You are the Supervisor agent. Plan briefly, then call tools.
- Prefer read/list actions first.
- Never delete/terminate resources.
- When creating/scaling, always specify namespace and replica count.
- If ambiguous, ask ONE short clarifying question.
- Output concise results."""

TOOLS = [
    k8s_list_namespaces,
    k8s_list_pods,
    k8s_pod_logs,
    k8s_create_deployment,
    k8s_scale_deployment,
]

def build_agent_v1():
    model = os.getenv("MODEL", "ollama:llama3.1:8b")

    agent = create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM,
        # Todo: middleware=[]  # (guardrails, summaries, approvals, etc.)
    )
    return agent
