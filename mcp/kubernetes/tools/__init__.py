"""
Tool registration helpers for the Kubernetes MCP server.
"""

from typing import TYPE_CHECKING, Callable, List

from . import (
    create_deployment,
    diagnostics,
    delete_deployment,
    delete_pod,
    list_namespaces,
    list_nodes,
    list_pods,
    pod_events,
    pod_logs,
    scale_deployment,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP

_REGISTRARS: List[Callable[["FastMCP"], None]] = [
    list_namespaces.register,
    list_nodes.register,
    list_pods.register,
    pod_logs.register,
    pod_events.register,
    create_deployment.register,
    scale_deployment.register,
    diagnostics.register,
    delete_deployment.register,
    delete_pod.register,
]


def register_all(mcp: "FastMCP") -> None:
    for register in _REGISTRARS:
        register(mcp)
