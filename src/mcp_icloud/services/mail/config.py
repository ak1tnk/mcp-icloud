"""Mail settings, read from the environment on every tool call."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

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
    f"iCloud Mail is not configured. Set {USER_ENV} to your iCloud email address and "
    f"{PASSWORD_ENV} to an app-specific password (create one at https://account.apple.com "
    "under Sign-In and Security > App-Specific Passwords), then restart the MCP server."
)


class MailNotConfigured(Exception):
    def __init__(self) -> None:
        super().__init__(NOT_CONFIGURED_MESSAGE)


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
        user = os.environ.get(USER_ENV, "").strip()
        password = os.environ.get(PASSWORD_ENV, "").strip()
        if not user or not password:
            raise MailNotConfigured()
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
