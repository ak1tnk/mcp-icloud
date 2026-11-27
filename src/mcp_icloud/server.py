"""stdio MCP server. Registers each service module's tools."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudException

from mcp_icloud import config
from mcp_icloud.services import hidemyemail, mail
from mcp_icloud.session import NotLoggedInError, is_auth_error, load_api

T = TypeVar("T")


class ApiProvider:
    def __init__(self, loader: Callable[[], PyiCloudService] = load_api):
        self._lock = Lock()
        self._loader = loader
        self._api: PyiCloudService | None = None

    def call(self, fn: Callable[[PyiCloudService], T]) -> T:
        with self._lock:
            try:
                return self._call(fn)
            except Exception as exc:
                if is_auth_error(exc):
                    self._api = None
                    message = (
                        str(exc)
                        if isinstance(exc, NotLoggedInError)
                        else str(NotLoggedInError(config.session_dir()))
                    )
                    raise ToolError(message) from exc
                if isinstance(exc, PyiCloudException):
                    raise ToolError(f"iCloud request failed: {type(exc).__name__}: {exc}") from exc
                raise

    def _call(self, fn: Callable[[PyiCloudService], T]) -> T:
        if self._api is None:
            self._api = self._loader()
            return fn(self._api)
        try:
            return fn(self._api)
        except Exception as exc:
            if not is_auth_error(exc):
                raise
        # The cached web cookies expired; reloading renews them from the stored session and
        # trust tokens without a password. The rejected request did not run, so retry once.
        self._api = self._loader()
        return fn(self._api)


def build_server(provider: ApiProvider | None = None) -> MCPServer:
    server = MCPServer(
        "mcp-icloud",
        instructions=(
            "Manages iCloud Hide My Email addresses (hme_*: generating a candidate does not "
            "save it; there is no delete) and iCloud Mail (mail_*: trash moves to Trash; "
            "send, reply and forward send immediately)."
        ),
    )
    provider = provider or ApiProvider()
    hidemyemail.register(server, provider)
    mail.register(server, provider)
    return server


def main() -> int:
    build_server().run()
    return 0
