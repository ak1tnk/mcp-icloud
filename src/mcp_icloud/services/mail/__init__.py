"""iCloud Mail over IMAP/SMTP with an app-specific password (no pyicloud session needed)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from mcp_icloud.services.mail import compose, reads


def register(server: MCPServer) -> None:
    reads.register(server)
    compose.register(server)
