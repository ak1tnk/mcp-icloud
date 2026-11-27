"""Shared helpers for the web mail backend (pyicloud's experimental Mail service).

Messages are identified exactly as on the IMAP backend: decoded mailbox name + UID.
Every web operation runs inside ``provider.call(lambda api: ...)`` so session errors become the
usual "run `mcp-icloud login`" tool error, and inside ``web_errors()`` for Mail errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from pyicloud.services.mail import MailFolder, MailMessage, MailService

SpecialKind = Literal["inbox", "drafts", "sent", "trash", "junk", "archive"]

UNSUPPORTED_HINT = (
    "Set up the IMAP backend with `mcp-icloud mail-login` (app-specific password) to use it."
)


@contextmanager
def web_errors() -> Iterator[None]:
    """MailWriteUncertain → ToolError saying the outcome is uncertain and to check Sent/Drafts
    (or the destination) before any retry; other MailError and pyicloud ValueError → ToolError
    with a short message. ToolError and session errors pass through unchanged."""
    raise NotImplementedError  # implemented in the web-read slice
    yield  # pragma: no cover


def display_name(folder: MailFolder) -> str:
    """The folder's Unicode name as shown to agents (raw server names may be IMAP modified
    UTF-7; decode with ``imap.decode_mailbox_name``)."""
    raise NotImplementedError  # implemented in the web-read slice


def special_use(folder: MailFolder) -> str | None:
    """Special use of iCloud's well-known folders, else None: INBOX → "\\Inbox", Drafts →
    "\\Drafts", Sent Messages → "\\Sent", Deleted Messages → "\\Trash", Junk → "\\Junk",
    Archive → "\\Archive"."""
    raise NotImplementedError  # implemented in the web-read slice


def folder(service: MailService, name: str) -> MailFolder:
    """The folder whose display name equals ``name``. Raises ToolError if there is none."""
    raise NotImplementedError  # implemented in the web-read slice


def special_folder(service: MailService, kind: SpecialKind) -> MailFolder:
    """The well-known folder of ``kind``. Raises ToolError if it does not exist."""
    raise NotImplementedError  # implemented in the web-read slice


def message(service: MailService, mailbox: str, uid: int) -> MailMessage:
    """The message with ``uid`` in the folder named ``mailbox`` (``message_by_uid``).
    Raises ToolError if there is no such message."""
    raise NotImplementedError  # implemented in the web-read slice
