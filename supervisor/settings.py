import os
from dotenv import load_dotenv
load_dotenv()

MODEL = os.getenv("MODEL", "ollama:llama3.1:8b")


MCP_SERVERS = {
    "kubernetes": os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080"),
}

ALLOWED_TOOLS = {
    "kubernetes": {
        "list_namespaces",
        "list_pods",
        "pod_logs",
        "create_deployment",
        "scale_deployment",
    }
}
