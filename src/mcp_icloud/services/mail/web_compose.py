"""Compose mail through the shared iCloud web session."""

from __future__ import annotations

import os
from email import policy
from email.parser import HeaderParser
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.services.mail import MailDraft, MailMessage, MailService
from pyicloud.services.mail.exceptions import MailWriteRejected

from mcp_icloud.services.mail import compose, web
from mcp_icloud.services.mail.config import USER_ENV, policy_settings

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider


def _sender(service: MailService, address: str | None, aliases: tuple[str, ...]) -> str:
    enabled = [sender.address for sender in service.senders()]
    main = os.environ.get(USER_ENV, "").strip() or (enabled[0] if enabled else "")
    allowed = (main, *aliases)
    sender = main if address is None else address
    if sender.lower() not in {item.lower() for item in allowed}:
        raise ToolError("From must be one of: " + ", ".join(allowed))
    if sender.lower() not in {item.lower() for item in enabled}:
        raise ToolError("From must be an enabled sender: " + ", ".join(enabled))
    return sender


def _uploads(service: MailService, paths: list[str] | None, limit: int) -> tuple:
    return tuple(
        service.upload_draft_attachment(data, filename=filename, content_type=content_type)
        for data, content_type, filename in compose._files(paths, limit)
    )


def _send(
    service: MailService, draft: MailDraft, sender: str, envelope: list[str]
) -> dict[str, Any]:
    try:
        service.send_draft(draft, confirm=True)
    except MailWriteRejected as exc:
        raise ToolError("Not sent: iCloud rejected the message; it was left in Drafts.") from exc
    return {"sent": True, "message_id": draft.message.id, "from": sender, "recipients": envelope}


def _envelope(allowlist: tuple[str, ...], addresses: list[str]) -> list[str]:
    envelope = compose._unique(addresses)
    if not envelope:
        raise ToolError("At least one recipient is required")
    compose._blocked(allowlist, envelope)
    return envelope


def _original(service: MailService, original: MailMessage) -> tuple[Any, str | None]:
    body = service.body(original)
    headers = HeaderParser(policy=policy.default).parsestr(body.headers)
    text = next(
        (
            part.content
            for meta in original.parts
            if meta.content_type.split(";", 1)[0].strip().lower() == "text/plain"
            for part in body.parts
            if part.guid.endswith(meta.id)
        ),
        None,
    )
    return headers, text


def send(
    provider: ApiProvider,
    *,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    from_address: str | None = None,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    def operation(api: Any) -> dict[str, Any]:
        service = api.mail
        aliases, allowlist, limit = policy_settings()
        sender = _sender(service, from_address, aliases)
        to_list, cc_list, bcc_list = map(compose._addresses, (to, cc, bcc))
        envelope = _envelope(allowlist, to_list + cc_list + bcc_list)
        draft = service.create_draft(
            sender=sender,
            subject=subject,
            text=body,
            to=tuple(to_list),
            cc=tuple(cc_list),
            bcc=tuple(bcc_list),
            attachments=_uploads(service, attachments, limit),
        )
        return _send(service, draft, sender, envelope)

    with web.web_errors():
        return provider.call(operation)


def reply(
    provider: ApiProvider,
    *,
    mailbox: str,
    uid: int,
    body: str,
    reply_all: bool = False,
    from_address: str | None = None,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    def operation(api: Any) -> dict[str, Any]:
        service = api.mail
        aliases, allowlist, limit = policy_settings()
        sender = _sender(service, from_address, aliases)
        original = web.message(service, mailbox, uid)
        headers, text = _original(service, original)
        to = compose._addresses([str(headers.get("Reply-To", headers.get("From", "")))])
        cc = (
            compose._addresses(headers.get_all("To", []) + headers.get_all("Cc", []))
            if reply_all
            else []
        )
        own = {s.address.lower() for s in service.senders()} | set(aliases)
        envelope = _envelope(allowlist, [a for a in to + cc if a.lower() not in own])
        to = [a for a in envelope if a.lower() in {item.lower() for item in to}]
        cc = [a for a in envelope if a not in to]
        quoted = body
        if text is not None:
            quoted += (
                f"\n\nOn {headers.get('Date', '')}, {headers.get('From', '')} wrote:\n"
                + "\n".join("> " + line for line in text.splitlines())
            )
        draft = service.create_reply_draft(
            original,
            sender=sender,
            to=tuple(to),
            cc=tuple(cc),
            text=quoted,
            attachments=_uploads(service, attachments, limit),
        )
        return {**_send(service, draft, sender, envelope), "in_reply_to": headers.get("Message-ID")}

    with web.web_errors():
        return provider.call(operation)


def forward(
    provider: ApiProvider,
    *,
    mailbox: str,
    uid: int,
    to: list[str],
    body: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    from_address: str | None = None,
    include_attachments: bool = True,
) -> dict[str, Any]:
    def operation(api: Any) -> dict[str, Any]:
        service = api.mail
        aliases, allowlist, _ = policy_settings()
        sender = _sender(service, from_address, aliases)
        to_list, cc_list, bcc_list = map(compose._addresses, (to, cc, bcc))
        envelope = _envelope(allowlist, to_list + cc_list + bcc_list)
        original = web.message(service, mailbox, uid)
        headers, text = _original(service, original)
        forwarded = body + "\n\n---------- Forwarded message ----------\n"
        forwarded += "".join(
            f"{key}: {headers.get(key, '')}\n" for key in ("From", "Date", "Subject", "To")
        )
        forwarded += "\n" + (text or "")
        draft = service.create_forward_draft(
            original,
            sender=sender,
            to=tuple(to_list),
            cc=tuple(cc_list),
            bcc=tuple(bcc_list),
            text=forwarded,
            include_original_attachments=include_attachments,
        )
        return _send(service, draft, sender, envelope)

    with web.web_errors():
        return provider.call(operation)


def save_draft(
    provider: ApiProvider,
    *,
    to: list[str] | None = None,
    subject: str = "",
    body: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    from_address: str | None = None,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    def operation(api: Any) -> dict[str, Any]:
        service = api.mail
        aliases, _, limit = policy_settings()
        sender = _sender(service, from_address, aliases)
        to_list, cc_list, bcc_list = map(compose._addresses, (to, cc, bcc))
        draft = service.create_draft(
            sender=sender,
            subject=subject,
            text=body,
            to=tuple(to_list),
            cc=tuple(cc_list),
            bcc=tuple(bcc_list),
            attachments=_uploads(service, attachments, limit),
        )
        return {
            "saved_as_draft": True,
            "mailbox": web.display_name(draft.message.folder),
            "message_id": draft.message.id,
        }

    with web.web_errors():
        return provider.call(operation)
