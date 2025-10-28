from typing import List, TYPE_CHECKING

from kubernetes.client import exceptions as k8s_exceptions

try:
    from ..kube_client import core_v1
except ImportError:  # pragma: no cover
    from kube_client import core_v1  # type: ignore

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: "FastMCP") -> None:
    @mcp.tool()
    def list_pods(namespace: str) -> List[str]:
        """List pods in a namespace."""
        try:
            return [pod.metadata.name for pod in core_v1().list_namespaced_pod(namespace).items]
        except k8s_exceptions.ApiException as exc:
            if exc.status == 404:
                raise ValueError(f"Namespace '{namespace}' not found") from exc
            raise
