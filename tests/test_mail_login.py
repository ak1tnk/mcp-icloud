import imaplib
import json
import smtplib
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call

import pytest
from pyicloud.exceptions import PyiCloudConnectionException

from mcp_icloud import cli, login
from mcp_icloud.services.mail.config import write_mail_login
from mcp_icloud.session import NotLoggedInError

USER = "you@example.com"
PASSWORD = "xxxx-xxxx-xxxx-xxxx"


@pytest.fixture
def connections(monkeypatch):
    calls = Mock()
    monkeypatch.setattr(login.imaplib, "IMAP4_SSL", calls.imap)
    monkeypatch.setattr(login.smtplib, "SMTP", calls.smtp)
    monkeypatch.setattr(login.getpass, "getpass", Mock(return_value=PASSWORD))
    monkeypatch.setattr("builtins.input", Mock(return_value=""))
    return calls


@pytest.mark.parametrize("source", ["argument", "environment", "account"])
def test_mail_login(connections, monkeypatch, session_dir, capsys, source):
    if source == "environment":
        monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", USER)
    elif source == "account":
        session_dir.mkdir()
        (session_dir / "account.json").write_text(json.dumps({"apple_id": USER}))
    args = ["mail-login", "--user", USER] if source == "argument" else ["mail-login"]
    assert cli.main(args) == 0
    path = session_dir / "mail.json"
    assert json.loads(path.read_text()) == {"user": USER, "app_password": PASSWORD}
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert connections.mock_calls == [
        call.imap("imap.mail.me.com", 993, ssl_context=ANY, timeout=30),
        call.imap().login(USER, PASSWORD),
        call.imap().logout(),
        call.smtp("smtp.mail.me.com", 587, timeout=30),
        call.smtp().starttls(context=ANY),
        call.smtp().login(USER, PASSWORD),
        call.smtp().quit(),
    ]
    login.getpass.getpass.assert_called_once_with("App-specific password: ")
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    assert f"Mail configured for {USER}. Stored in {path}." in output.out


def test_empty_address(connections, session_dir):
    assert login.mail_login_command(None) == 2
    assert not (session_dir / "mail.json").exists()
    login.getpass.getpass.assert_not_called()
    assert not connections.mock_calls


@pytest.mark.parametrize("protocol", ["imap", "smtp", "network"])
def test_failed_login(connections, session_dir, capsys, protocol):
    if protocol == "imap":
        connections.imap.return_value.login.side_effect = imaplib.IMAP4.error(PASSWORD)
    elif protocol == "smtp":
        connections.smtp.return_value.login.side_effect = smtplib.SMTPException(PASSWORD)
    else:
        connections.imap.side_effect = OSError(PASSWORD)
    assert login.mail_login_command(USER) == 1
    assert not (session_dir / "mail.json").exists()
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    assert "Could not verify the Mail login: ***" in output.err


@pytest.mark.parametrize("exists", [False, True])
def test_mail_logout(session_dir, capsys, exists):
    if exists:
        write_mail_login(USER, PASSWORD)
    assert cli.main(["mail-logout"]) == 0
    assert not (session_dir / "mail.json").exists()
    output = capsys.readouterr().out
    assert ("Removed the stored Mail password." if exists else "No stored Mail password.") in output
    assert "https://account.apple.com." in output
    assert PASSWORD not in output


@pytest.mark.parametrize("source", ["none", "file", "environment"])
@pytest.mark.parametrize("outcome", ["ok", "missing", "connection"])
def test_mail_status(monkeypatch, session_dir, capsys, source, outcome):
    if source == "file":
        write_mail_login(USER, PASSWORD)
    elif source == "environment":
        monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", USER)
        monkeypatch.setenv("MCP_ICLOUD_MAIL_APP_PASSWORD", PASSWORD)
    loader = Mock(return_value=SimpleNamespace(account_name=USER))
    if outcome == "missing":
        loader.side_effect = NotLoggedInError(session_dir)
    elif outcome == "connection":
        loader.side_effect = PyiCloudConnectionException("offline")
    monkeypatch.setattr(login, "load_api", loader)
    assert login.status_command() == (0 if outcome == "ok" else 1)
    expected = "Mail: web backend (uses the mcp-icloud login session; experimental)"
    if source != "none":
        location = "environment" if source == "environment" else str(session_dir / "mail.json")
        expected = f"Mail: IMAP backend, configured for {USER} ({location})"
    output = capsys.readouterr()
    assert expected in output.out.splitlines()
    assert PASSWORD not in output.out + output.err


@pytest.mark.parametrize(
    "backend,expected",
    [
        ("imap", "Mail: IMAP backend, not configured (run mcp-icloud mail-login)"),
        ("web", "Mail: web backend (uses the mcp-icloud login session; experimental)"),
        ("bogus", "Mail: MCP_ICLOUD_MAIL_BACKEND must be auto, web or imap, not 'bogus'"),
    ],
)
def test_status_mail_backend(monkeypatch, capsys, backend, expected):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_BACKEND", backend)
    monkeypatch.setattr(login, "load_api", Mock(side_effect=NotLoggedInError(Path("/x"))))
    login.status_command()
    assert expected in capsys.readouterr().out.splitlines()
