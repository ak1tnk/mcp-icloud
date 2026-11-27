"""Where the session lives and how it is protected.

The Apple ID password is read from env only by the agent login tools.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

SESSION_DIR_ENV = "MCP_ICLOUD_SESSION_DIR"
APPLE_ID_ENV = "MCP_ICLOUD_APPLE_ID"
PASSWORD_ENV = "MCP_ICLOUD_APPLE_PASSWORD"  # noqa: S105 - env var name, not a secret
ACCOUNT_FILE = "account.json"


def session_dir() -> Path:
    """$MCP_ICLOUD_SESSION_DIR, else $XDG_CONFIG_HOME/mcp-icloud, else ~/.config/mcp-icloud."""
    explicit = os.environ.get(SESSION_DIR_ENV)
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "mcp-icloud"


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` if needed; force 0700 on it and 0600 on every regular file in it."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    for child in path.iterdir():
        if child.is_file() and not child.is_symlink():
            child.chmod(0o600)
    return path


def is_private(path: Path) -> bool:
    """True if ``path`` and its regular files grant nothing to group or others."""
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        return False
    return all(
        not (stat.S_IMODE(c.stat().st_mode) & 0o077)
        for c in path.iterdir()
        if c.is_file() and not c.is_symlink()
    )


def stored_apple_id(directory: Path) -> str | None:
    """$MCP_ICLOUD_APPLE_ID, else the apple_id in <dir>/account.json, else None."""
    env = os.environ.get(APPLE_ID_ENV)
    if env:
        return env
    account = directory / ACCOUNT_FILE
    if not account.is_file():
        return None
    value = json.loads(account.read_text(encoding="utf-8")).get("apple_id")
    return value if isinstance(value, str) and value else None


def write_apple_id(directory: Path, apple_id: str) -> None:
    """Write <dir>/account.json (0600). Holds the Apple ID only, never a password."""
    ensure_private_dir(directory)
    account = directory / ACCOUNT_FILE
    fd = os.open(account, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"apple_id": apple_id}, fh)
    account.chmod(0o600)
