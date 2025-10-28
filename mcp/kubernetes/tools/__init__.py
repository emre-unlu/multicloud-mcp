"""
Tool registration helpers for the Kubernetes MCP server.
"""

from typing import TYPE_CHECKING, Callable, List

from . import (
    create_deployment,
    diagnostics,
    list_namespaces,
    list_pods,
    pod_logs,
    scale_deployment,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP

_REGISTRARS: List[Callable[["FastMCP"], None]] = [
    list_namespaces.register,
    list_pods.register,
    pod_logs.register,
    create_deployment.register,
    scale_deployment.register,
    diagnostics.register,
]


def register_all(mcp: "FastMCP") -> None:
    for register in _REGISTRARS:
        register(mcp)
