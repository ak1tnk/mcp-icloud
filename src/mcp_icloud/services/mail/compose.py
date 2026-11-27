"""Mail tools that create messages: send, reply, forward, save draft."""

from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail import imap
from mcp_icloud.services.mail.config import SMTP_HOST, SMTP_PORT, MailConfig
from mcp_icloud.services.mail.errors import mail_errors

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider


def _sender(cfg: MailConfig, address: str | None) -> str:
    allowed = (cfg.user, *cfg.from_aliases)
    if address is None:
        return cfg.user
    if address.lower() not in {item.lower() for item in allowed}:
        raise ToolError("From must be one of: " + ", ".join(allowed))
    return address


def _addresses(entries: list[str] | None) -> list[str]:
    result: list[str] = []
    for entry in entries or []:
        parsed = getaddresses([entry])
        if not parsed or any("@" not in address for _, address in parsed):
            raise ToolError("Each recipient must contain an email address with @")
        result.extend(address for _, address in parsed)
    return result


def _unique(addresses: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for address in addresses:
        if address.lower() not in seen:
            seen.add(address.lower())
            result.append(address)
    return result


def _files(paths: list[str] | None, limit: int) -> list[tuple[bytes, str, str | None]]:
    result: list[tuple[bytes, str, str | None]] = []
    total = 0
    for value in paths or []:
        path = Path(value)
        if not path.is_absolute() or not path.is_file():
            raise ToolError("Attachments must be absolute paths to existing regular files")
        total += path.stat().st_size
        if total > limit:  # checked before reading, so a huge file is never loaded
            raise ToolError("Total attachment bytes exceed the configured limit")
        result.append(
            (
                path.read_bytes(),
                mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                path.name,
            )
        )
    return result


def _message(
    cfg: MailConfig,
    sender: str,
    to: list[str],
    cc: list[str],
    subject: str,
    body: str,
    attachments: list[tuple[bytes, str, str | None]],
) -> EmailMessage:
    if sum(len(data) for data, _, _ in attachments) > cfg.max_attachment_bytes:
        raise ToolError("Total attachment bytes exceed the configured limit")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[1])
    msg.set_content(body, charset="utf-8")
    for data, content_type, filename in attachments:
        maintype, subtype = content_type.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def _send(cfg: MailConfig, msg: EmailMessage, envelope: list[str]) -> dict[str, Any]:
    if not envelope:
        raise ToolError("At least one recipient is required")
    blocked = [
        address
        for address in envelope
        if cfg.send_allowlist
        and not any(
            address.lower() == entry.lower()
            or (entry.startswith("@") and address.lower().endswith(entry.lower()))
            for entry in cfg.send_allowlist
        )
    ]
    if blocked:
        raise ToolError(
            "Not sent: these recipients are not on MCP_ICLOUD_SEND_ALLOWLIST: " + ", ".join(blocked)
        )
    sender = str(msg["From"])
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg.user, cfg.password)
        smtp.send_message(msg, from_addr=sender, to_addrs=envelope)
    return {
        "sent": True,
        "message_id": str(msg["Message-ID"]),
        "from": sender,
        "recipients": envelope,
    }


def _original(cfg: MailConfig, mailbox: str, uid: int) -> EmailMessage:
    with imap.connect(cfg) as conn:
        imap.select(conn, mailbox, readonly=True)
        return imap.fetch_message(conn, uid)


def _text(msg: EmailMessage) -> str | None:
    part = msg.get_body(preferencelist=("plain",))
    return str(part.get_content()) if part is not None else None


def register(server: MCPServer, provider: ApiProvider) -> None:
    @server.tool()
    def mail_send(
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        from_address: str | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a message immediately, with optional attachments."""
        with mail_errors():
            cfg = MailConfig.from_env()
            sender = _sender(cfg, from_address)
            to, cc, bcc = _addresses(to), _addresses(cc), _addresses(bcc)
            msg = _message(
                cfg, sender, to, cc, subject, body, _files(attachments, cfg.max_attachment_bytes)
            )
            return _send(cfg, msg, _unique(to + cc + bcc))

    @server.tool()
    def mail_reply(
        mailbox: str,
        uid: int,
        body: str,
        reply_all: bool = False,
        from_address: str | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a reply immediately, optionally to all original recipients."""
        with mail_errors():
            cfg = MailConfig.from_env()
            sender = _sender(cfg, from_address)
            original = _original(cfg, mailbox, uid)
            to = _addresses([str(original.get("Reply-To", original.get("From", "")))])
            cc = []
            if reply_all:
                cc = _addresses(original.get_all("To", []) + original.get_all("Cc", []))
            own = {address.lower() for address in (cfg.user, *cfg.from_aliases)}
            recipients = _unique([address for address in to + cc if address.lower() not in own])
            to = [
                address
                for address in recipients
                if address.lower() in {item.lower() for item in to}
            ]
            cc = [address for address in recipients if address not in to]
            subject = str(original.get("Subject", ""))
            if not subject.lower().startswith("re:"):
                subject = "Re: " + subject
            text = _text(original)
            if text is not None:
                body += (
                    f"\n\nOn {original.get('Date', '')}, {original.get('From', '')} wrote:\n"
                    + "\n".join("> " + line for line in text.splitlines())
                )
            msg = _message(
                cfg, sender, to, cc, subject, body, _files(attachments, cfg.max_attachment_bytes)
            )
            message_id = str(original.get("Message-ID", ""))
            if message_id:
                msg["In-Reply-To"] = message_id
            references = " ".join(filter(None, [str(original.get("References", "")), message_id]))
            if references:
                msg["References"] = references
            return {**_send(cfg, msg, recipients), "in_reply_to": message_id}

    @server.tool()
    def mail_forward(
        mailbox: str,
        uid: int,
        to: list[str],
        body: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        from_address: str | None = None,
        include_attachments: bool = True,
    ) -> dict[str, Any]:
        """Forward a message immediately, optionally including its attachments."""
        with mail_errors():
            cfg = MailConfig.from_env()
            sender = _sender(cfg, from_address)
            to, cc, bcc = _addresses(to), _addresses(cc), _addresses(bcc)
            original = _original(cfg, mailbox, uid)
            subject = str(original.get("Subject", ""))
            if not subject.lower().startswith(("fwd:", "fw:")):
                subject = "Fwd: " + subject
            body += "\n\n---------- Forwarded message ----------\n"
            body += "".join(
                f"{key}: {original.get(key, '')}\n" for key in ("From", "Date", "Subject", "To")
            )
            body += "\n" + (_text(original) or "")
            files = []
            if include_attachments:
                for part in original.iter_attachments():
                    files.append(
                        (
                            cast(bytes, part.get_payload(decode=True)) or b"",
                            part.get_content_type(),
                            part.get_filename(),
                        )
                    )
            msg = _message(cfg, sender, to, cc, subject, body, files)
            return _send(cfg, msg, _unique(to + cc + bcc))

    @server.tool()
    def mail_save_draft(
        to: list[str] | None = None,
        subject: str = "",
        body: str = "",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        from_address: str | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a message in Drafts without sending it."""
        with mail_errors():
            cfg = MailConfig.from_env()
            sender = _sender(cfg, from_address)
            to, cc, bcc_list = _addresses(to), _addresses(cc), _addresses(bcc)
            msg = _message(
                cfg, sender, to, cc, subject, body, _files(attachments, cfg.max_attachment_bytes)
            )
            if bcc_list:  # kept in the draft so it is not lost; drafts are never sent from here
                msg["Bcc"] = ", ".join(bcc_list)
            with imap.connect(cfg) as conn:
                mailbox = imap.special_mailbox(conn, "\\Drafts", "Drafts")
                imap.append(conn, mailbox, "(\\Draft \\Seen)", msg)
            return {
                "saved_as_draft": True,
                "mailbox": mailbox,
                "message_id": str(msg["Message-ID"]),
            }
