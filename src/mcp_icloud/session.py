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

from mcp_icloud import config

# Status codes Apple uses for an expired or untrusted web session (pyicloud may pass int or str).
_AUTH_STATUS_CODES = {"401", "421", "450"}
# pyicloud rewrites the reason to this for 409/421/450/500 failures; a 500 is usually transient.
_AUTH_REQUIRED_REASON = "Authentication required for Account."


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
        code = str(exc.code)
        return code in _AUTH_STATUS_CODES or (exc.reason == _AUTH_REQUIRED_REASON and code != "500")
    return False


def load_api() -> PyiCloudService:
    """Return an authenticated PyiCloudService from the stored session.

    Raises NotLoggedInError when there is no usable session.
    """
    directory = config.session_dir()
    apple_id = config.stored_apple_id(directory)
    if apple_id is None:
        raise NotLoggedInError(directory)
    config.ensure_private_dir(directory)
    try:
        api = PyiCloudService(
            apple_id, password=None, cookie_directory=str(directory), authenticate=False
        )
        api.authenticate()
    except Exception as exc:
        if is_auth_error(exc):
            raise NotLoggedInError(directory) from exc
        raise
    if api.requires_2fa or api.requires_2sa or not api.is_trusted_session:
        raise NotLoggedInError(directory)
    return api
