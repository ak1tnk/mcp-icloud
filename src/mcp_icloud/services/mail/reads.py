"""Mail tools that read or reorganize existing messages."""

from __future__ import annotations

import os
import re
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail import imap, web_reads
from mcp_icloud.services.mail.backend import selected_backend
from mcp_icloud.services.mail.config import MailConfig
from mcp_icloud.services.mail.errors import mail_errors

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider

SPECIAL = ("\\Inbox", "\\Drafts", "\\Sent", "\\Trash", "\\Junk", "\\Archive", "\\All", "\\Flagged")


def _uids(uids: list[int]) -> str:
    if not 1 <= len(uids) <= 500 or any(type(uid) is not int or uid <= 0 for uid in uids):
        raise ToolError("uids must contain 1 to 500 positive integers")
    return ",".join(map(str, uids))


def _ok(result: Any, context: str) -> Any:
    status, data = result
    if status != "OK":
        raise ToolError(context)
    return data


def _date(message: EmailMessage) -> str:
    raw = str(message.get("Date", ""))
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (ValueError, TypeError, OverflowError):
        return raw


def _headers(message: EmailMessage) -> dict[str, Any]:
    return {
        "date": _date(message),
        **{
            key: str(message.get(key.replace("_", "-"), ""))
            for key in ("from", "to", "cc", "subject")
        },
    }


class _HTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self.hidden += 1
        if not self.hidden and tag in (
            "p",
            "div",
            "br",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "section",
            "blockquote",
            "pre",
            "ul",
            "ol",
            "table",
        ):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden:
            self.handle_starttag(tag, [])

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _content(part: EmailMessage) -> bytes:
    raw = part.get_payload(decode=True)
    return raw if isinstance(raw, bytes) else part.as_bytes()


def _move(conn: Any, mailbox: str, uids: list[int], destination: str) -> dict[str, Any]:
    sequence = _uids(uids)
    if destination not in [box.name for box in imap.list_mailboxes(conn)]:
        raise ToolError(f"Mailbox {destination} not found")
    if "MOVE" not in {
        c.decode().upper() if isinstance(c, bytes) else c.upper() for c in conn.capabilities
    }:
        raise ToolError("Server does not support MOVE")
    imap.select(conn, mailbox, readonly=False)
    _ok(
        conn.uid("MOVE", sequence, imap._quote_mailbox(destination)),
        f"Could not move uids {sequence} from {mailbox}",
    )
    return {"mailbox": mailbox, "uids": uids, "destination": destination}


def register(server: MCPServer, provider: ApiProvider) -> None:
    @server.tool()
    def mail_list_mailboxes() -> dict[str, Any]:
        """List mailboxes and their special uses."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.list_mailboxes(provider)
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                return {
                    "mailboxes": [
                        {
                            "name": b.name,
                            "special_use": "\\Inbox"
                            if b.name.upper() == "INBOX"
                            else next((f for f in SPECIAL if f in b.flags), None),
                            "flags": list(b.flags),
                        }
                        for b in imap.list_mailboxes(conn)
                    ]
                }

    @server.tool()
    def mail_search(
        mailbox: str = "INBOX",
        sender: str | None = None,
        recipient: str | None = None,
        subject: str | None = None,
        text: str | None = None,
        since: str | None = None,
        before: str | None = None,
        unread_only: bool = False,
        flagged_only: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search mail and return the newest matching message headers."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.search(
                    provider,
                    mailbox=mailbox,
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    text=text,
                    since=since,
                    before=before,
                    unread_only=unread_only,
                    flagged_only=flagged_only,
                    limit=limit,
                )
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                if not 1 <= limit <= 100:
                    raise ToolError("limit must be 1 to 100")
                criteria = []
                literal = None
                for key, value in (
                    ("FROM", sender),
                    ("TO", recipient),
                    ("SUBJECT", subject),
                    ("TEXT", text),
                ):
                    if value is None:
                        continue
                    if not value.isascii():
                        if literal is not None:
                            raise ToolError(
                                "Only one non-ASCII search term is supported per search."
                            )
                        literal = (key, value.encode("utf-8"))
                    else:
                        criteria.extend(
                            [key, '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"']
                        )
                for key, value in (("SINCE", since), ("BEFORE", before)):
                    if value is not None:
                        try:
                            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                                raise ValueError
                            date = datetime.strptime(value, "%Y-%m-%d")
                        except ValueError:
                            raise ToolError("Dates must use YYYY-MM-DD") from None
                        month = (
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec",
                        )[date.month - 1]
                        criteria.extend([key, f"{date.day:02}-{month}-{date.year:04}"])
                if unread_only:
                    criteria.append("UNSEEN")
                if flagged_only:
                    criteria.append("FLAGGED")
                imap.select(conn, mailbox, readonly=True)
                if literal:
                    criteria.append(literal[0])
                    cast(Any, conn).literal = literal[1]
                rows = _ok(
                    conn.uid(
                        "SEARCH", *(["CHARSET", "UTF-8"] if literal else []), *(criteria or ["ALL"])
                    ),
                    f"Could not search mailbox {mailbox}",
                )
                matches = sorted(
                    {int(uid) for row in rows if row for uid in row.split()}, reverse=True
                )
                messages = []
                if matches:
                    wanted = matches[:limit]
                    fetched = _ok(
                        conn.uid(
                            "FETCH",
                            ",".join(map(str, wanted)),
                            "(UID FLAGS RFC822.SIZE "
                            "BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE)])",
                        ),
                        f"Could not fetch headers from {mailbox}",
                    )
                    for row in fetched:
                        if not isinstance(row, tuple):
                            continue
                        meta, header_bytes = row
                        uid_match = re.search(rb"UID (\d+)", meta)
                        size = re.search(rb"RFC822.SIZE (\d+)", meta)
                        flags = re.search(rb"FLAGS \((.*?)\)", meta)
                        if uid_match:
                            flags_raw = flags.group(1).split() if flags else []
                            messages.append(
                                {
                                    "uid": int(uid_match.group(1)),
                                    **_headers(
                                        BytesParser(policy=policy.default).parsebytes(header_bytes)
                                    ),
                                    "seen": b"\\Seen" in flags_raw,
                                    "flagged": b"\\Flagged" in flags_raw,
                                    "size": int(size.group(1)) if size else 0,
                                }
                            )
                return {
                    "mailbox": mailbox,
                    "total_matches": len(matches),
                    "messages": sorted(messages, key=lambda m: m["uid"], reverse=True),
                }

    @server.tool()
    def mail_read(
        mailbox: str, uid: int, max_chars: int = 20000, mark_read: bool = False
    ) -> dict[str, Any]:
        """Read a message and list its attachments. Optionally mark it read."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.read(
                    provider, mailbox=mailbox, uid=uid, max_chars=max_chars, mark_read=mark_read
                )
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                _uids([uid])
                if not 1 <= max_chars <= 200000:
                    raise ToolError("max_chars must be 1 to 200000")
                imap.select(conn, mailbox, readonly=not mark_read)
                message = imap.fetch_message(conn, uid)
                body = message.get_body(preferencelist=("plain", "html"))
                text = str(body.get_content()) if body else ""
                if body and body.get_content_type() == "text/html":
                    parser = _HTML()
                    parser.feed(text)
                    text = re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
                if mark_read:
                    _ok(
                        conn.uid("STORE", str(uid), "+FLAGS", "(\\Seen)"),
                        f"Could not mark uid {uid} read",
                    )
                return {
                    "mailbox": mailbox,
                    "uid": uid,
                    **_headers(message),
                    **{
                        key: str(message.get(key.replace("_", "-"), ""))
                        for key in ("message_id", "reply_to", "in_reply_to")
                    },
                    "text": text[:max_chars],
                    "text_truncated": len(text) > max_chars,
                    "attachments": [
                        {
                            "index": i,
                            "filename": p.get_filename(),
                            "content_type": p.get_content_type(),
                            "size": len(_content(p)),
                        }
                        for i, p in enumerate(message.iter_attachments())
                    ],
                }

    @server.tool()
    def mail_download_attachment(mailbox: str, uid: int, index: int, path: str) -> dict[str, Any]:
        """Download an attachment to a new absolute file with private permissions."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.download_attachment(
                    provider, mailbox=mailbox, uid=uid, index=index, path=path
                )
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                _uids([uid])
                target = Path(path)
                if not target.is_absolute() or target.exists() or not target.parent.is_dir():
                    raise ToolError("path must be absolute, new, and have an existing parent")
                imap.select(conn, mailbox, readonly=True)
                parts = list(imap.fetch_message(conn, uid).iter_attachments())
                if not 0 <= index < len(parts):
                    raise ToolError("Invalid attachment index")
                part = parts[index]
                data = _content(part)
                if len(data) > cfg.max_attachment_bytes:
                    raise ToolError("Attachment exceeds size limit")
                with os.fdopen(
                    os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
                ) as file:
                    file.write(data)
                return {
                    "path": path,
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                    "size": len(data),
                }

    @server.tool()
    def mail_set_flags(
        mailbox: str, uids: list[int], seen: bool | None = None, flagged: bool | None = None
    ) -> dict[str, Any]:
        """Set or clear the read and flagged status of messages."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.set_flags(
                    provider, mailbox=mailbox, uids=uids, seen=seen, flagged=flagged
                )
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                sequence = _uids(uids)
                if seen is None and flagged is None:
                    raise ToolError("Provide seen or flagged")
                imap.select(conn, mailbox, readonly=False)
                for value, flag in ((seen, "\\Seen"), (flagged, "\\Flagged")):
                    if value is not None:
                        _ok(
                            conn.uid(
                                "STORE", sequence, "+FLAGS" if value else "-FLAGS", f"({flag})"
                            ),
                            f"Could not set flags for uids {sequence} in {mailbox}",
                        )
                return {"mailbox": mailbox, "uids": uids, "seen": seen, "flagged": flagged}

    @server.tool()
    def mail_move(mailbox: str, uids: list[int], destination: str) -> dict[str, Any]:
        """Move messages to an existing mailbox."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.move(provider, mailbox=mailbox, uids=uids, destination=destination)
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                return _move(conn, mailbox, uids, destination)

    @server.tool()
    def mail_archive(mailbox: str, uids: list[int]) -> dict[str, Any]:
        """Move messages to the Archive mailbox."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.archive(provider, mailbox=mailbox, uids=uids)
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                return _move(
                    conn, mailbox, uids, imap.special_mailbox(conn, "\\Archive", "Archive")
                )

    @server.tool()
    def mail_trash(mailbox: str, uids: list[int]) -> dict[str, Any]:
        """Move messages to Trash without deleting them permanently."""
        with mail_errors():
            if selected_backend() == "web":
                return web_reads.trash(provider, mailbox=mailbox, uids=uids)
            cfg = MailConfig.from_env()
            with imap.connect(cfg) as conn:
                return _move(
                    conn, mailbox, uids, imap.special_mailbox(conn, "\\Trash", "Deleted Messages")
                )
