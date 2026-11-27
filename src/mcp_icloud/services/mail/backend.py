"""Pick the mail backend for each tool call: IMAP/SMTP or the iCloud web API via pyicloud."""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail.config import configured_mail

BACKEND_ENV = "MCP_ICLOUD_MAIL_BACKEND"

Backend = Literal["imap", "web"]


def selected_backend() -> Backend:
    """auto (default): IMAP when an app-specific password is configured (environment or
    mail.json), otherwise the web backend through the `mcp-icloud login` session."""
    value = os.environ.get(BACKEND_ENV, "").strip().lower() or "auto"
    if value == "auto":
        return "imap" if configured_mail() else "web"
    if value in ("imap", "web"):
        return value  # type: ignore[return-value]
    raise ToolError(f"{BACKEND_ENV} must be auto, web or imap, not {value!r}")
