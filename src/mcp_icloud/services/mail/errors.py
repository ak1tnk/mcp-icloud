"""Turn mail failures into tool errors that never contain the app-specific password."""

from __future__ import annotations

import imaplib
import os
import smtplib
from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail.config import PASSWORD_ENV, MailNotConfigured


def _scrub(text: str) -> str:
    password = os.environ.get(PASSWORD_ENV, "").strip()
    return text.replace(password, "***") if password else text


@contextmanager
def mail_errors() -> Iterator[None]:
    """Wrap one tool body: config, IMAP, SMTP and network errors become ToolError."""
    try:
        yield
    except ToolError:
        raise
    except MailNotConfigured as exc:
        raise ToolError(str(exc)) from None
    except imaplib.IMAP4.error as exc:
        raise ToolError(_scrub(f"IMAP error: {exc}")) from None
    except smtplib.SMTPException as exc:
        raise ToolError(_scrub(f"SMTP error: {type(exc).__name__}: {exc}")) from None
    except OSError as exc:
        raise ToolError(_scrub(f"Network error talking to iCloud Mail: {exc}")) from None
