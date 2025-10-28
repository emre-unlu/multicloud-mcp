from typing import Optional, TYPE_CHECKING

from kubernetes.client import exceptions as k8s_exceptions

try:
    from ..kube_client import core_v1
except ImportError:  # pragma: no cover
    from kube_client import core_v1  # type: ignore

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: "FastMCP") -> None:
    @mcp.tool()
    def pod_logs(namespace: str, pod: str, tail_lines: int = 80) -> str:
        """Get the last N log lines for a pod."""
        try:
            return core_v1().read_namespaced_pod_log(
                name=pod,
                namespace=namespace,
                tail_lines=tail_lines,
            )
        except k8s_exceptions.ApiException as exc:
            if exc.status == 404:
                raise ValueError(f"Pod '{pod}' in namespace '{namespace}' not found") from exc
            raise
