"""Read and organize mail through the shared pyicloud session."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from email import policy
from email.parser import HeaderParser
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail import web
from mcp_icloud.services.mail.config import DEFAULT_MAX_ATTACHMENT_MB, MAX_ATTACHMENT_ENV

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider


def list_mailboxes(provider: ApiProvider) -> dict[str, Any]:
    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            return {
                "mailboxes": [
                    {"name": web.display_name(b), "special_use": web.special_use(b), "flags": []}
                    for b in api.mail.folders()
                    if "$category$" not in web.display_name(b)  # iCloud-internal, always empty
                ]
            }

    return provider.call(run)


def _date(message: Any) -> datetime | None:
    value = message.internal_date
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, UTC)


def search(
    provider: ApiProvider,
    *,
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
    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            if not 1 <= limit <= 100:
                raise ToolError("limit must be 1 to 100")
            terms = [
                (k, v)
                for k, v in (
                    ("from", sender),
                    ("to", recipient),
                    ("subject", subject),
                    ("all", text),
                )
                if v is not None
            ]
            if sum(not v.isascii() for _, v in terms) > 1:
                raise ToolError(
                    "Only one non-ASCII search term is supported per search. "
                    + web.UNSUPPORTED_HINT
                )
            dates = []
            for value in (since, before):
                try:
                    if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                    dates.append(
                        datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
                        if value is not None
                        else None
                    )
                except ValueError:
                    raise ToolError("Dates must use YYYY-MM-DD") from None
            if (
                len(terms) > 1
                or (unread_only and flagged_only)
                or (terms and (unread_only or flagged_only))
            ):
                raise ToolError(
                    "Web mail cannot combine search criteria or flag filters. "
                    + web.UNSUPPORTED_HINT
                )
            service = api.mail
            box = web.folder(service, mailbox)
            if terms:
                field, value = terms[0]
                hits = service.search(box, value, field=field, limit=limit).results
                source = (
                    m
                    for hit in hits
                    for m in service.thread_messages(box, hit.id, limit=limit).messages
                )
            elif unread_only or flagged_only:
                source = service.iter_filtered_messages(
                    box, filter_by="unread" if unread_only else "flagged", page_size=50
                )
            elif since or before:
                source = service.iter_messages(box, page_size=50)
            else:
                source = service.messages(box, limit=limit).messages
            collected = {}
            for m in islice(source, 1000):
                date = _date(m)
                if dates[0] and date and date < dates[0]:
                    if not terms:
                        break
                    continue
                if (since or before) and date is None:
                    raise ToolError(
                        "Web mail cannot date-filter messages without internal dates. "
                        + web.UNSUPPORTED_HINT
                    )
                if dates[1] and date and date >= dates[1]:
                    continue
                collected[m.uid] = {
                    "uid": m.uid,
                    "date": date.isoformat() if date else None,
                    "from": m.sender,
                    "to": m.to,
                    "cc": m.cc,
                    "subject": m.subject or "",
                    "size": m.size or 0,
                    "seen": False if unread_only else None,
                    "flagged": True if flagged_only else None,
                }
            return {
                "mailbox": mailbox,
                "total_matches": len(collected),
                "messages": [collected[k] for k in sorted(collected, reverse=True)[:limit]],
            }

    return provider.call(run)


def read(
    provider: ApiProvider,
    *,
    mailbox: str,
    uid: int,
    max_chars: int = 20000,
    mark_read: bool = False,
) -> dict[str, Any]:
    from mcp_icloud.services.mail.reads import _HTML, _uids

    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            _uids([uid])
            if not 1 <= max_chars <= 200000:
                raise ToolError("max_chars must be 1 to 200000")
            m = web.message(api.mail, mailbox, uid)
            try:
                body = api.mail.body(m)
            except ValueError as exc:
                if "no supported text body parts" not in str(exc):
                    raise
                body = None
            headers = HeaderParser(policy=policy.default).parsestr(body.headers if body else "")
            candidates = []
            for b in body.parts if body else []:
                part = next((p for p in m.parts if b.guid.endswith("-" + p.id)), None)
                kind = part.content_type.split(";", 1)[0].strip().lower() if part else ""
                candidates.append(
                    (0 if kind == "text/plain" else 1 if kind == "text/html" else 2, b.content)
                )
            rank, content = min(candidates, key=lambda c: c[0]) if candidates else (2, "")
            if rank == 1:
                parser = _HTML()
                parser.feed(content)
                content = re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
            date = _date(m)
            fallback = {
                "message_id": m.id,
                "date": date.isoformat() if date else "",
                "from": m.sender or "",
                "to": m.to or "",
                "cc": m.cc or "",
                "subject": m.subject or "",
                "reply_to": "",
                "in_reply_to": "",
            }
            result_headers = {
                k: str(headers.get(k.replace("_", "-"), v)) for k, v in fallback.items()
            }
            if "Date" in headers:
                from email.utils import parsedate_to_datetime

                try:
                    result_headers["date"] = parsedate_to_datetime(str(headers["Date"])).isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass
            if mark_read:
                api.mail.set_read(m, read=True)
            return {
                "mailbox": mailbox,
                "uid": uid,
                **result_headers,
                "text": content[:max_chars],
                "text_truncated": len(content) > max_chars,
                "attachments": [
                    {
                        "index": i,
                        "filename": p.filename,
                        "content_type": p.content_type,
                        "size": p.size,
                    }
                    for i, p in enumerate(p for p in m.parts if p.is_attachment)
                ],
            }

    return provider.call(run)


def download_attachment(
    provider: ApiProvider, *, mailbox: str, uid: int, index: int, path: str
) -> dict[str, Any]:
    from mcp_icloud.services.mail.reads import _uids

    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            _uids([uid])
            target = Path(path)
            if not target.is_absolute() or target.exists() or not target.parent.is_dir():
                raise ToolError("path must be absolute, new, and have an existing parent")
            m = web.message(api.mail, mailbox, uid)
            parts = [p for p in m.parts if p.is_attachment]
            if not 0 <= index < len(parts):
                raise ToolError("Invalid attachment index")
            p = parts[index]
            max_mb = os.environ.get(MAX_ATTACHMENT_ENV, "").strip()
            limit = (
                int(float(max_mb) * 1024 * 1024)
                if max_mb
                else DEFAULT_MAX_ATTACHMENT_MB * 1024 * 1024
            )
            if p.size is not None and p.size > limit:
                raise ToolError("Attachment exceeds size limit")
            stream = (
                api.mail.mail_drop_attachment(m, m.parts.index(p) + 1, max_bytes=limit)
                if p.is_mail_drop
                else api.mail.attachment(m, p.id)
            )
            total = 0
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as file, stream as chunks:
                    for chunk in chunks:
                        total += len(chunk)
                        if total > limit:
                            raise ToolError("Attachment exceeds size limit")
                        file.write(chunk)
            except BaseException:
                target.unlink()
                raise
            return {
                "path": path,
                "filename": p.filename,
                "content_type": p.content_type,
                "size": total,
            }

    return provider.call(run)


def set_flags(
    provider: ApiProvider,
    *,
    mailbox: str,
    uids: list[int],
    seen: bool | None = None,
    flagged: bool | None = None,
) -> dict[str, Any]:
    from mcp_icloud.services.mail.reads import _uids

    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            _uids(uids)
            if seen is None and flagged is None:
                raise ToolError("Provide seen or flagged")
            for uid in uids:
                m = web.message(api.mail, mailbox, uid)
                if seen is not None:
                    api.mail.set_read(m, read=seen)
                if flagged is not None:
                    api.mail.set_flagged(m, flagged=flagged)
            return {"mailbox": mailbox, "uids": uids, "seen": seen, "flagged": flagged}

    return provider.call(run)


def move(
    provider: ApiProvider, *, mailbox: str, uids: list[int], destination: str
) -> dict[str, Any]:
    return _move(provider, mailbox, uids, destination, None)


def archive(provider: ApiProvider, *, mailbox: str, uids: list[int]) -> dict[str, Any]:
    return _move(provider, mailbox, uids, None, "archive")


def trash(provider: ApiProvider, *, mailbox: str, uids: list[int]) -> dict[str, Any]:
    return _move(provider, mailbox, uids, None, "trash")


def _move(
    provider: ApiProvider,
    mailbox: str,
    uids: list[int],
    destination: str | None,
    special: web.SpecialKind | None,
) -> dict[str, Any]:
    from mcp_icloud.services.mail.reads import _uids

    def run(api: Any) -> dict[str, Any]:
        with web.web_errors():
            _uids(uids)
            dest = (
                web.special_folder(api.mail, special)
                if special
                else web.folder(api.mail, str(destination))
            )
            for uid in uids:
                api.mail.move(web.message(api.mail, mailbox, uid), dest)
            return {"mailbox": mailbox, "uids": uids, "destination": web.display_name(dest)}

    return provider.call(run)
