import imaplib
import smtplib

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail.config import MailConfig, MailNotConfigured
from mcp_icloud.services.mail.errors import mail_errors

FAKE_PASSWORD = "xxxx-xxxx-xxxx-xxxx"


def test_not_configured() -> None:
    with pytest.raises(MailNotConfigured, match="MCP_ICLOUD_MAIL_APP_PASSWORD"):
        MailConfig.from_env()


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", "you@example.com")
    monkeypatch.setenv("MCP_ICLOUD_MAIL_APP_PASSWORD", FAKE_PASSWORD)
    monkeypatch.setenv("MCP_ICLOUD_MAIL_FROM_ALIASES", " Alias@Example.com, ,other@example.com")
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", "@example.org, friend@example.net")
    monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", "1.5")
    cfg = MailConfig.from_env()
    assert cfg.user == "you@example.com"
    assert cfg.from_aliases == ("alias@example.com", "other@example.com")
    assert cfg.send_allowlist == ("@example.org", "friend@example.net")
    assert cfg.max_attachment_bytes == int(1.5 * 1024 * 1024)
    assert FAKE_PASSWORD not in repr(cfg)


@pytest.mark.parametrize(
    "exc",
    [
        imaplib.IMAP4.error(f"login failed for {FAKE_PASSWORD}"),
        smtplib.SMTPAuthenticationError(535, f"bad {FAKE_PASSWORD}".encode()),
        OSError(f"reset {FAKE_PASSWORD}"),
        MailNotConfigured(),
    ],
)
def test_mail_errors_become_tool_errors_without_password(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    monkeypatch.setenv("MCP_ICLOUD_MAIL_APP_PASSWORD", FAKE_PASSWORD)
    with pytest.raises(ToolError) as info, mail_errors():
        raise exc
    assert FAKE_PASSWORD not in str(info.value)
