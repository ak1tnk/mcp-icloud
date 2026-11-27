"""Mail tools that read or reorganize existing messages."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register(server: MCPServer) -> None:
    pass  # implemented in the mail-read slice
