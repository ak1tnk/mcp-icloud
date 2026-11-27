import stat
from pathlib import Path

from mcp_icloud import config


def test_session_dir_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_ICLOUD_SESSION_DIR", str(tmp_path / "explicit"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.session_dir() == tmp_path / "explicit"
    monkeypatch.delenv("MCP_ICLOUD_SESSION_DIR")
    assert config.session_dir() == tmp_path / "xdg" / "mcp-icloud"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert config.session_dir() == Path.home() / ".config" / "mcp-icloud"


def test_stored_apple_id(monkeypatch, session_dir):
    assert config.stored_apple_id(session_dir) is None
    config.write_apple_id(session_dir, "file@example.com")
    assert config.stored_apple_id(session_dir) == "file@example.com"
    monkeypatch.setenv("MCP_ICLOUD_APPLE_ID", "env@example.com")
    assert config.stored_apple_id(session_dir) == "env@example.com"


def test_write_private(session_dir):
    config.write_apple_id(session_dir, "a@example.com")
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((session_dir / "account.json").stat().st_mode) == 0o600


def test_tighten_permissions(session_dir):
    session_dir.mkdir()
    session_dir.chmod(0o755)
    file = session_dir / "example.session"
    file.write_text("example")
    file.chmod(0o644)
    config.ensure_private_dir(session_dir)
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
