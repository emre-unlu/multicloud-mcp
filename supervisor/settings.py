import os
from dotenv import load_dotenv
load_dotenv()

# LLM choice:
#   MODEL="openai:gpt-4o-mini" with OPENAI_API_KEY set
#   or MODEL="ollama:llama3.1:8b" with OLLAMA running locally
MODEL = os.getenv("MODEL", "openai:gpt-4o-mini")

# Worker MCP URLs (ROOT, no path). Add more clouds here later.
MCP_SERVERS = {
    "kubernetes": os.getenv("K8S_MCP_URL", "http://127.0.0.1:8080"),
}

# Safety: which tools are allowed on which worker
ALLOWED_TOOLS = {
    "kubernetes": {
        "list_namespaces",
        "list_pods",
        "pod_logs",
        "create_deployment",
        "scale_deployment",
    }
}
