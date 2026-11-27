"""iCloud Mail over IMAP/SMTP with an app-specific password (no pyicloud session needed)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from mcp_icloud.services.mail import compose, reads

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider


def register(server: MCPServer, provider: ApiProvider) -> None:
    """``provider`` is the shared pyicloud session, used by the web backend."""
    reads.register(server, provider)
    compose.register(server, provider)
