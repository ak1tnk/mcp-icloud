"""IMAP helpers shared by the read and compose tools. Message ids are (mailbox, UID)."""

from __future__ import annotations

import base64
import imaplib
import re
import ssl
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail.config import IMAP_HOST, IMAP_PORT, MailConfig


@dataclass(frozen=True)
class Mailbox:
    name: str  # decoded (Unicode) name, as shown to the agent
    flags: tuple[str, ...]  # e.g. ("\\HasNoChildren", "\\Drafts")


def encode_mailbox_name(name: str) -> str:
    """Unicode → IMAP modified UTF-7 (RFC 3501 §5.1.3)."""
    chunks = []
    pending: list[str] = []

    def flush():
        if pending:
            raw = "".join(pending).encode("utf-16-be")
            chunks.append("&" + base64.b64encode(raw).decode().rstrip("=").replace("/", ",") + "-")
            pending.clear()

    for char in name:
        if " " <= char <= "~":
            flush()
            chunks.append("&-" if char == "&" else char)
        else:
            pending.append(char)
    flush()
    return "".join(chunks)


def decode_mailbox_name(name: str) -> str:
    """IMAP modified UTF-7 → Unicode."""

    def decode(match):
        value = match.group(1)
        if not value:
            return "&"
        value = value.replace(",", "/")
        return base64.b64decode(value + "=" * (-len(value) % 4)).decode("utf-16-be")

    return re.sub(r"&([^-]*)-", decode, name)


@contextmanager
def connect(cfg: MailConfig) -> Iterator[imaplib.IMAP4_SSL]:
    """Open a TLS IMAP connection to iCloud, log in, and log out on exit."""
    conn = imaplib.IMAP4_SSL(
        IMAP_HOST, IMAP_PORT, ssl_context=ssl.create_default_context(), timeout=30
    )
    try:
        conn.login(cfg.user, cfg.password)
        yield conn
    finally:
        with suppress(Exception):
            conn.logout()


def list_mailboxes(conn: imaplib.IMAP4) -> list[Mailbox]:
    status, rows = conn.list()
    if status != "OK":
        raise ToolError("Could not list mailboxes")
    result = []
    for row in rows:
        if row is None:
            continue
        prefix = row[0] if isinstance(row, tuple) else row
        match = re.match(rb'\((.*?)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(.*)', prefix)
        if not match:
            continue
        raw = row[1] if isinstance(row, tuple) else match.group(2)
        if raw.startswith(b'"') and raw.endswith(b'"'):
            raw = re.sub(rb"\\(.)", rb"\1", raw[1:-1])
        result.append(
            Mailbox(
                decode_mailbox_name(raw.decode("ascii")), tuple(match.group(1).decode().split())
            )
        )
    return result


def special_mailbox(conn: imaplib.IMAP4, flag: str, fallback: str) -> str:
    """Decoded name of the mailbox with special-use ``flag`` (e.g. "\\Drafts"), else ``fallback``
    if it exists. Raises ToolError if neither exists."""
    boxes = list_mailboxes(conn)
    for box in boxes:
        if flag in box.flags:
            return box.name
    if any(box.name == fallback for box in boxes):
        return fallback
    raise ToolError(f"Mailbox {fallback} not found")


def select(conn: imaplib.IMAP4, name: str, *, readonly: bool) -> None:
    """Select the mailbox with decoded ``name``. Raises ToolError if it does not exist."""
    status, _ = conn.select(_quote_mailbox(name), readonly=readonly)
    if status != "OK":
        raise ToolError(f"Could not select mailbox {name}")


def fetch_message(conn: imaplib.IMAP4, uid: int) -> EmailMessage:
    """Fetch the full message by UID from the selected mailbox without setting \\Seen.
    Raises ToolError if there is no such message."""
    status, rows = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if status == "OK":
        for row in rows:
            if isinstance(row, tuple) and isinstance(row[1], bytes):
                return BytesParser(policy=policy.default).parsebytes(row[1])
    raise ToolError(f"Could not fetch uid {uid}")


def append(conn: imaplib.IMAP4, name: str, flags: str, message: EmailMessage) -> None:
    """Append ``message`` to the mailbox with decoded ``name`` with ``flags`` like
    "(\\Draft \\Seen)". Raises ToolError if the server refuses."""
    status, _ = conn.append(
        _quote_mailbox(name), flags, imaplib.Time2Internaldate(time.time()), message.as_bytes()
    )
    if status != "OK":
        raise ToolError(f"Could not append to mailbox {name}")


def _quote_mailbox(name: str) -> str:
    return '"' + encode_mailbox_name(name).replace("\\", "\\\\").replace('"', '\\"') + '"'
