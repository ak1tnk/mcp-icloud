"""Every test runs offline, against a temp session dir, with keyring disabled."""

from __future__ import annotations

import socket
from pathlib import Path

import keyring
import pytest
import requests.adapters


def _blocked(*args: object, **kwargs: object) -> None:
    raise RuntimeError("network access is disabled in tests")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(keyring, "get_password", _blocked)
    monkeypatch.setattr(keyring, "set_password", _blocked)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    session = tmp_path / "session"
    monkeypatch.setenv("MCP_ICLOUD_SESSION_DIR", str(session))
    monkeypatch.delenv("MCP_ICLOUD_APPLE_ID", raising=False)
    for name in (
        "MCP_ICLOUD_APPLE_PASSWORD",
        "MCP_ICLOUD_MAIL_USER",
        "MCP_ICLOUD_MAIL_APP_PASSWORD",
        "MCP_ICLOUD_MAIL_FROM_ALIASES",
        "MCP_ICLOUD_SEND_ALLOWLIST",
        "MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB",
    ):
        monkeypatch.delenv(name, raising=False)
    return session


@pytest.fixture
def session_dir(_isolate: Path) -> Path:
    """The (not yet created) session directory every test points at."""
    return _isolate


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
