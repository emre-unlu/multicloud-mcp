# Using AIOpsLab to create intentional Kubernetes faults

This repository can target clusters that AIOpsLab provisions and manages. Use AIOpsLab's problem catalog to inject known faults and then point the diagnostics worker at the impacted cluster.

## 1) Stand up AIOpsLab
1. Clone the upstream repo and create or target a Kubernetes cluster (local [kind](https://kind.sigs.k8s.io/) works well):
   ```bash
   git clone https://github.com/microsoft/AIOpsLab.git
   cd AIOpsLab
   # for local clusters on x86
   kind create cluster --config kind/kind-config-x86.yaml
   cp config.yml.example config.yml
   # set k8s_host/k8s_user in config.yml to match your control plane host
   ```
   Refer to the AIOpsLab README for remote cluster options and additional setup details.
2. Start the FastAPI service that exposes the problem catalog:
   ```bash
   SERVICE_HOST=0.0.0.0 SERVICE_PORT=1818 python service.py
   ```
   The service exposes endpoints such as `/health`, `/problems`, and `/simulate`.

## 2) Discover and trigger faults
Use the lightweight helper in this repo to browse available problems and initialize one against the running AIOpsLab service.
You only need Python 3.9+ and the `requests` dependency (installable via `pip install requests` if your environment does not
already include it).

From the root of this repository:
```bash
# 1) (first time only) install the single runtime dependency for the helper
python -m pip install --user requests

# 2) List available problems (fault scenarios) from the AIOpsLab FastAPI service
python -m supervisor.aiopslab --service-url http://127.0.0.1:1818 --list-problems

# 3) Initialize a problem without letting the bundled agent attempt a fix
python -m supervisor.aiopslab \
  --service-url http://127.0.0.1:1818 \
  --problem-id k8s_target_port-misconfig-mitigation-1 \
  --max-steps 0
```

Passing `--max-steps 0` leaves the injected fault in place so you can point the diagnostics worker at the cluster and verify detection. If you want the upstream AIOpsLab agent to attempt a fix, increase `--max-steps` and (optionally) pass agent-specific parameters such as `--temperature` and `--model`.

## 3) Diagnose with this repository
Ensure the MCP Kubernetes server in this repo is pointed at the same cluster (via your kubeconfig). Then run the supervisor UI and issue a diagnostics request as usual. The cluster will already contain the AIOpsLab scenario you initialized.