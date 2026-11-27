"""Agent login using server environment settings and a user-provided 2FA code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAccountLockedException,
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudNoTrustedNumberAvailable,
    PyiCloudTrustedDevicePromptException,
    PyiCloudTrustedDeviceVerificationException,
)

from mcp_icloud import config
from mcp_icloud.session import NotLoggedInError, load_api

PENDING_TTL_SECONDS = 600
MAX_CODE_ATTEMPTS = 3


@dataclass
class PendingLogin:
    api: PyiCloudService
    apple_id: str
    directory: Path
    deadline: float
    attempts: int = 0


_pending: PendingLogin | None = None
_lock = Lock()


def _error_message(exc: Exception) -> str:
    if isinstance(exc, PyiCloudAccountLockedException):
        return (
            "Apple reports this Apple ID as locked. Ask the user to unlock it at "
            "https://iforgot.apple.com. Do not call icloud_login_start again until the user "
            "confirms it is unlocked."
        )
    if isinstance(exc, PyiCloudFailedLoginException):
        return (
            "Apple rejected the Apple ID or password from MCP_ICLOUD_APPLE_ID / "
            "MCP_ICLOUD_APPLE_PASSWORD. Ask the user to correct the secret in the agent "
            "platform's settings (never in chat). Do not call icloud_login_start again until "
            "the user has fixed it: repeated failures can lock the Apple ID."
        )
    if isinstance(exc, PyiCloudNoTrustedNumberAvailable):
        return "Two-factor authentication needs a trusted phone number, but Apple returned none."
    if isinstance(
        exc, PyiCloudTrustedDevicePromptException | PyiCloudTrustedDeviceVerificationException
    ):
        return "Apple rejected the trusted-device 2FA step. Call icloud_login_start again."
    if isinstance(exc, PyiCloudConnectionException):
        return "Could not reach Apple. Check the network and retry."
    return f"Login failed: {type(exc).__name__}."


def _finish(api: PyiCloudService, directory: Path, apple_id: str) -> dict[str, str]:
    global _pending
    if not api.is_trusted_session:
        api.trust_session()
    if not api.is_trusted_session:
        _pending = None
        raise ToolError(
            "Apple accepted the code but did not trust this session. Call icloud_login_start again."
        ) from None
    config.write_apple_id(directory, apple_id)
    config.ensure_private_dir(directory)
    _pending = None
    return {
        "status": "logged_in",
        "apple_id": apple_id,
        "session_dir": str(directory),
        "message": (
            f"Logged in as {apple_id}. Session saved in {directory}. The iCloud tools are ready."
        ),
    }


def icloud_login_start() -> dict[str, str]:
    """Sign in to iCloud with MCP_ICLOUD_APPLE_ID and MCP_ICLOUD_APPLE_PASSWORD from this server's environment (the user stores them in the agent platform's secret store). If Apple sends a 2FA code, ask the user for it and call icloud_login_verify. Never ask the user for their password in chat."""  # noqa: E501
    global _pending
    with _lock:
        apple_id = os.environ.get(config.APPLE_ID_ENV, "").strip()
        password = os.environ.get(config.PASSWORD_ENV, "").strip()
        if not apple_id or not password:
            _pending = None
            raise ToolError(
                "MCP_ICLOUD_APPLE_ID and MCP_ICLOUD_APPLE_PASSWORD must both be set in this "
                "MCP server's environment. Ask the user to add them as secrets/environment "
                "variables of this MCP server in the agent platform's connector settings "
                "(never in chat), restart or reconnect the server, then call icloud_login_start "
                "again. Without them, the user can run `mcp-icloud login` in a terminal instead."
            ) from None
        message = None
        try:
            api = load_api()
        except NotLoggedInError:
            pass
        except PyiCloudConnectionException:
            message = "Could not reach Apple. Check the network and retry."
        except Exception:  # noqa: S110 - any other failure means no usable session
            pass
        else:
            _pending = None
            return {
                "status": "already_logged_in",
                "apple_id": api.account_name,
                "message": f"Already logged in as {api.account_name}; nothing to do. "
                "The iCloud tools are ready.",
            }
        _pending = None
        if message:
            raise ToolError(message) from None
        try:
            directory = config.session_dir()
            config.ensure_private_dir(directory)
            api = PyiCloudService(apple_id, password, cookie_directory=str(directory))
            config.ensure_private_dir(directory)
            if api.requires_2fa:
                fallback = False
                try:
                    requested = api.request_2fa_code()
                except PyiCloudConnectionException:
                    raise
                except PyiCloudTrustedDevicePromptException:
                    raise
                except PyiCloudAPIResponseException:
                    api.use_existing_trusted_device_code()
                    requested = True
                    fallback = True
                if requested is False:
                    message = (
                        "This Apple ID needs a security key for two-factor authentication, "
                        "which mcp-icloud does not support. Use an Apple ID with code-based 2FA."
                    )
                else:
                    _pending = PendingLogin(
                        api, apple_id, directory, monotonic() + PENDING_TTL_SECONDS
                    )
                    result = {
                        "status": "code_sent",
                        "delivery": api.two_factor_delivery_method,
                        "message": (
                            "Apple could not send a new 2FA code. If a trusted Apple device of "
                            "the user already shows a code, ask the user for it and call "
                            "icloud_login_verify; otherwise call icloud_login_start again later."
                            if fallback
                            else "Apple sent a 2FA code to the user's trusted Apple devices "
                            "(or by SMS). Ask the user for the 6-digit code, then call "
                            "icloud_login_verify with it. The code request expires in 10 minutes."
                        ),
                    }
                    if api.two_factor_delivery_notice:
                        result["notice"] = api.two_factor_delivery_notice
                    return result
            elif api.requires_2sa:
                message = (
                    "This Apple ID uses legacy two-step verification, which is not supported. "
                    "Ask the user to turn on two-factor authentication for the Apple ID."
                )
            else:
                return _finish(api, directory, apple_id)
        except ToolError as exc:
            message = str(exc)
        except Exception as exc:
            message = _error_message(exc)
        _pending = None
        raise ToolError(message) from None


def icloud_login_verify(code: str) -> dict[str, str]:
    """Finish the login started by icloud_login_start with the 6-digit 2FA code the user gave you. Saves the session so the iCloud tools work."""  # noqa: E501
    global _pending
    code = "".join(code.split())
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        raise ToolError(
            "The 2FA code must be 6 digits. Ask the user for the code shown on their device."
        ) from None
    with _lock:
        if _pending is None:
            raise ToolError(
                "No login is in progress (or the server was restarted). "
                "Call icloud_login_start first."
            ) from None
        if monotonic() > _pending.deadline:
            _pending = None
            raise ToolError(
                "The pending login expired after 10 minutes. Call icloud_login_start again "
                "to get a new code."
            ) from None
        message = None
        try:
            ok = _pending.api.validate_2fa_code(code)
        except PyiCloudConnectionException:
            message = "Could not reach Apple. Check the network and retry."
        except Exception as exc:
            message = (
                "Apple rejected the trusted-device 2FA step. Call icloud_login_start again."
                if isinstance(exc, PyiCloudTrustedDeviceVerificationException)
                else f"Login failed: {type(exc).__name__}."
            )
            _pending = None
        else:
            if not ok:
                _pending.attempts += 1
                if _pending.attempts >= MAX_CODE_ATTEMPTS:
                    _pending = None
                    message = (
                        "Apple did not accept the code 3 times. Call icloud_login_start again "
                        "for a new code."
                    )
                else:
                    message = (
                        "Apple did not accept that code. Ask the user to check the code and "
                        "call icloud_login_verify again, or call icloud_login_start for a new code."
                    )
            else:
                try:
                    return _finish(_pending.api, _pending.directory, _pending.apple_id)
                except ToolError as exc:
                    message = str(exc)
                except Exception as exc:
                    message = f"Login failed: {type(exc).__name__}."
                _pending = None
        raise ToolError(message) from None


def register(server: MCPServer) -> None:
    server.tool()(icloud_login_start)
    server.tool()(icloud_login_verify)
