"""Shared helpers for the web mail backend (pyicloud's experimental Mail service).

Messages are identified exactly as on the IMAP backend: decoded mailbox name + UID.
Every web operation runs inside ``provider.call(lambda api: ...)`` so session errors become the
usual "run `mcp-icloud login`" tool error, and inside ``web_errors()`` for Mail errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.services.mail import (
    MailError,
    MailFolder,
    MailMessage,
    MailService,
    MailWriteUncertain,
)

from mcp_icloud.services.mail import imap

SpecialKind = Literal["inbox", "drafts", "sent", "trash", "junk", "archive"]

UNSUPPORTED_HINT = (
    "Set up the IMAP backend with `mcp-icloud mail-login` (app-specific password) to use it."
)


@contextmanager
def web_errors() -> Iterator[None]:
    """MailWriteUncertain → ToolError saying the outcome is uncertain and to check Sent/Drafts
    (or the destination) before any retry; other MailError and pyicloud ValueError → ToolError
    with a short message. ToolError and session errors pass through unchanged."""
    try:
        yield
    except MailWriteUncertain:
        raise ToolError(
            "Mail outcome is uncertain; check Sent/Drafts or the destination before any retry."
        ) from None
    except (MailError, ValueError) as exc:
        raise ToolError(f"Mail error: {exc}") from None


def display_name(folder: MailFolder) -> str:
    """The folder's Unicode name as shown to agents (raw server names may be IMAP modified
    UTF-7; decode with ``imap.decode_mailbox_name``)."""
    return imap.decode_mailbox_name(folder.name)


def special_use(folder: MailFolder) -> str | None:
    """Special use of iCloud's well-known folders, else None: INBOX → "\\Inbox", Drafts →
    "\\Drafts", Sent Messages → "\\Sent", Deleted Messages → "\\Trash", Junk → "\\Junk",
    Archive → "\\Archive"."""
    return {
        "INBOX": "\\Inbox",
        "Drafts": "\\Drafts",
        "Sent Messages": "\\Sent",
        "Deleted Messages": "\\Trash",
        "Junk": "\\Junk",
        "Archive": "\\Archive",
    }.get(display_name(folder))


def folder(service: MailService, name: str) -> MailFolder:
    """The folder whose display name equals ``name``. Raises ToolError if there is none."""
    for item in service.folders():
        if display_name(item) == name:
            return item
    raise ToolError(f"Mailbox {name} not found")


def special_folder(service: MailService, kind: SpecialKind) -> MailFolder:
    """The well-known folder of ``kind``. Raises ToolError if it does not exist."""
    for item in service.folders():
        if special_use(item) == "\\" + kind.capitalize():
            return item
    raise ToolError(f"Mailbox {kind} not found")


def message(service: MailService, mailbox: str, uid: int) -> MailMessage:
    """The message with ``uid`` in the folder named ``mailbox`` (``message_by_uid``).
    Raises ToolError if there is no such message."""
    result = service.message_by_uid(folder(service, mailbox), uid)
    if result is None:
        raise ToolError(f"Could not fetch uid {uid}")
    return result
