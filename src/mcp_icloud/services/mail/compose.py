"""Mail tools that create messages: send, reply, forward, save draft."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register(server: MCPServer) -> None:
    pass  # implemented in the mail-compose slice
