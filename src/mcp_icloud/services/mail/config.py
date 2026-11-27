"""Mail settings, read from the environment on every tool call."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from mcp_icloud import config

USER_ENV = "MCP_ICLOUD_MAIL_USER"
PASSWORD_ENV = "MCP_ICLOUD_MAIL_APP_PASSWORD"  # noqa: S105 - env var name, not a secret
FROM_ALIASES_ENV = "MCP_ICLOUD_MAIL_FROM_ALIASES"
SEND_ALLOWLIST_ENV = "MCP_ICLOUD_SEND_ALLOWLIST"
MAX_ATTACHMENT_ENV = "MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB"

IMAP_HOST = "imap.mail.me.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.mail.me.com"
SMTP_PORT = 587
DEFAULT_MAX_ATTACHMENT_MB = 20

NOT_CONFIGURED_MESSAGE = (
    "iCloud Mail is not configured. Run mcp-icloud mail-login in a terminal, or set "
    f"{USER_ENV} to your iCloud email address and "
    f"{PASSWORD_ENV} to an app-specific password (create one at https://account.apple.com "
    "under Sign-In and Security > App-Specific Passwords), then restart the MCP server."
)


class MailNotConfigured(Exception):
    def __init__(self) -> None:
        super().__init__(NOT_CONFIGURED_MESSAGE)


def _stored_login() -> tuple[str, str] | None:
    path = config.session_dir() / "mail.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    user, password = data.get("user"), data.get("app_password")
    if isinstance(user, str) and user and isinstance(password, str) and password:
        return user, password
    return None


def configured_mail() -> tuple[str, str] | None:
    if os.environ.get(PASSWORD_ENV, "").strip():
        user = os.environ.get(USER_ENV, "").strip()
        return (user, "environment") if user else None
    stored = _stored_login()
    return (stored[0], str(config.session_dir() / "mail.json")) if stored else None


def write_mail_login(user: str, password: str) -> Path:
    directory = config.ensure_private_dir(config.session_dir())
    path = directory / "mail.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"user": user, "app_password": password}, fh)
    path.chmod(0o600)
    return path


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in (value or "").split(",") if item.strip())


@dataclass(frozen=True)
class MailConfig:
    user: str
    password: str = field(repr=False)
    from_aliases: tuple[str, ...] = ()
    send_allowlist: tuple[str, ...] = ()
    max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_MB * 1024 * 1024

    @classmethod
    def from_env(cls) -> MailConfig:
        """Read login from the environment first, then mail.json; other settings from env."""
        password = os.environ.get(PASSWORD_ENV, "").strip()
        if password:  # an empty variable counts as unset, so mail.json is used
            user = os.environ.get(USER_ENV, "").strip()
            if not user:
                raise MailNotConfigured()
        else:
            stored = _stored_login()
            if stored is None:
                raise MailNotConfigured()
            user, password = stored
        max_mb = os.environ.get(MAX_ATTACHMENT_ENV, "").strip()
        return cls(
            user=user,
            password=password,
            from_aliases=_csv(os.environ.get(FROM_ALIASES_ENV)),
            send_allowlist=_csv(os.environ.get(SEND_ALLOWLIST_ENV)),
            max_attachment_bytes=int(float(max_mb) * 1024 * 1024)
            if max_mb
            else DEFAULT_MAX_ATTACHMENT_MB * 1024 * 1024,
        )
