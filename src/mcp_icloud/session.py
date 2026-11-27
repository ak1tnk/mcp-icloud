"""Load the stored pyicloud session for the MCP server. Never asks for a password."""

from __future__ import annotations

from pathlib import Path

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloud2SARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudFailedLoginException,
)

# HTTP status codes Apple uses for an expired or untrusted web session.
_AUTH_STATUS_CODES = {401, 421, 450}


def not_logged_in_message(directory: Path) -> str:
    return (
        f"iCloud session is missing or expired (session directory: {directory}). "
        "On a machine with a terminal, run `mcp-icloud login` and complete 2FA. "
        "If this server runs on another machine (e.g. a Linux VM), then copy that "
        "session directory to it (keep it 0700, files 0600) or point "
        "MCP_ICLOUD_SESSION_DIR at the copy. Then retry."
    )


class NotLoggedInError(Exception):
    """No usable session: the owner must run `mcp-icloud login`."""

    def __init__(self, directory: Path) -> None:
        super().__init__(not_logged_in_message(directory))
        self.directory = directory


def is_auth_error(exc: BaseException) -> bool:
    """True if ``exc`` means the stored session is missing, expired or untrusted."""
    if isinstance(
        exc,
        NotLoggedInError
        | PyiCloudFailedLoginException
        | PyiCloudAuthRequiredException
        | PyiCloud2FARequiredException
        | PyiCloud2SARequiredException,
    ):
        return True
    if isinstance(exc, PyiCloudAPIResponseException):
        return getattr(exc, "code", None) in _AUTH_STATUS_CODES
    return False


def load_api() -> PyiCloudService:
    """Return an authenticated PyiCloudService from the stored session.

    Raises NotLoggedInError when there is no usable session.
    """
    raise NotImplementedError  # implemented in the auth slice
