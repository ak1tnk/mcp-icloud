"""IMAP helpers shared by the read and compose tools. Message ids are (mailbox, UID)."""

from __future__ import annotations

import imaplib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage

from mcp_icloud.services.mail.config import MailConfig


@dataclass(frozen=True)
class Mailbox:
    name: str  # decoded (Unicode) name, as shown to the agent
    flags: tuple[str, ...]  # e.g. ("\\HasNoChildren", "\\Drafts")


def encode_mailbox_name(name: str) -> str:
    """Unicode → IMAP modified UTF-7 (RFC 3501 §5.1.3)."""
    raise NotImplementedError  # implemented in the mail-read slice


def decode_mailbox_name(name: str) -> str:
    """IMAP modified UTF-7 → Unicode."""
    raise NotImplementedError  # implemented in the mail-read slice


@contextmanager
def connect(cfg: MailConfig) -> Iterator[imaplib.IMAP4_SSL]:
    """Open a TLS IMAP connection to iCloud, log in, and log out on exit."""
    raise NotImplementedError  # implemented in the mail-read slice
    yield  # pragma: no cover


def list_mailboxes(conn: imaplib.IMAP4) -> list[Mailbox]:
    raise NotImplementedError  # implemented in the mail-read slice


def special_mailbox(conn: imaplib.IMAP4, flag: str, fallback: str) -> str:
    """Decoded name of the mailbox with special-use ``flag`` (e.g. "\\Drafts"), else ``fallback``
    if it exists. Raises ToolError if neither exists."""
    raise NotImplementedError  # implemented in the mail-read slice


def select(conn: imaplib.IMAP4, name: str, *, readonly: bool) -> None:
    """Select the mailbox with decoded ``name``. Raises ToolError if it does not exist."""
    raise NotImplementedError  # implemented in the mail-read slice


def fetch_message(conn: imaplib.IMAP4, uid: int) -> EmailMessage:
    """Fetch the full message by UID from the selected mailbox without setting \\Seen.
    Raises ToolError if there is no such message."""
    raise NotImplementedError  # implemented in the mail-read slice


def append(conn: imaplib.IMAP4, name: str, flags: str, message: EmailMessage) -> None:
    """Append ``message`` to the mailbox with decoded ``name`` with ``flags`` like
    "(\\Draft \\Seen)". Raises ToolError if the server refuses."""
    raise NotImplementedError  # implemented in the mail-read slice
