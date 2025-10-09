import sys, logging
from typing import List, Dict, Optional
from fastmcp import FastMCP  # pip install fastmcp
from kubernetes import client, config

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP(
    name="kubernetes-mcp",
    instructions="Safe Kubernetes tools (no delete)."
)

_loaded = False
def _init():
    global _loaded
    if not _loaded:
        config.load_kube_config()  # uses ~/.kube/config (Docker Desktop)
        _loaded = True

def v1():
    _init(); return client.CoreV1Api()

def apps():
    _init(); return client.AppsV1Api()

@mcp.tool()
def list_namespaces() -> List[str]:
    """List Kubernetes namespaces."""
    return [n.metadata.name for n in v1().list_namespace().items]

@mcp.tool()
def list_pods(namespace: str) -> List[str]:
    """List pods in a namespace."""
    return [p.metadata.name for p in v1().list_namespaced_pod(namespace).items]

@mcp.tool()
def pod_logs(namespace: str, pod: str, tail_lines: int = 80) -> str:
    """Get last N log lines for a pod."""
    return v1().read_namespaced_pod_log(name=pod, namespace=namespace, tail_lines=tail_lines)

@mcp.tool()
def create_deployment(namespace: str, name: str, image: str = "nginx", replicas: int = 1) -> Dict:
    """Create a small deployment (replicas 1..5)."""
    if replicas < 1 or replicas > 5:
        raise ValueError("replicas must be between 1 and 5 for demo safety")
    body = {
        "apiVersion":"apps/v1","kind":"Deployment",
        "metadata":{"name":name},
        "spec":{"replicas":replicas,
            "selector":{"matchLabels":{"app":name}},
            "template":{"metadata":{"labels":{"app":name}},
                "spec":{"containers":[{"name":name,"image":image,"ports":[{"containerPort":80}]}]}
            }
        }
    }
    res = apps().create_namespaced_deployment(namespace, body)
    return {"name": res.metadata.name, "namespace": namespace, "replicas": res.spec.replicas}

@mcp.tool()
def scale_deployment(namespace: str, name: str, replicas: int) -> Dict:
    """Scale an existing deployment (replicas 1..5)."""
    if replicas < 1 or replicas > 5:
        raise ValueError("replicas must be between 1 and 5 for demo safety")
    res = apps().patch_namespaced_deployment_scale(name, namespace, {"spec":{"replicas":replicas}})
    return {"name": name, "namespace": namespace, "replicas": res.spec.replicas}

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8080,
        path="/",
        stateless_http=True,
    )   
