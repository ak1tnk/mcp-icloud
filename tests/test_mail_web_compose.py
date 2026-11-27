from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.services.mail.exceptions import MailWriteRejected
from pyicloud.services.mail.models import (
    MailBody,
    MailBodyPart,
    MailFolder,
    MailMessage,
    MailPart,
    MailSender,
)

from mcp_icloud.server import ApiProvider, build_server
from mcp_icloud.services.mail import web_compose
from mcp_icloud.session import NotLoggedInError


@pytest.fixture
def mail(monkeypatch):
    monkeypatch.delenv("MCP_ICLOUD_MAIL_BACKEND", raising=False)
    service = MagicMock()
    service.senders.return_value = [MailSender(address="you@example.com")]
    folder = MailFolder(id="drafts", name="Drafts")
    original = MailMessage(
        id="original",
        uid=1,
        mailbox={"id": "drafts"},
        folder=folder,
        parts=[MailPart(id="1", content_type="text/plain")],
    )
    service.body.return_value = MailBody(
        guid="original",
        headers=(
            "From: friend@example.com\nTo: you@example.com, other@example.com\n"
            "Cc: alias@example.com, OTHER@example.com\nSubject: Hello\n"
            "Date: Fri, 27 Nov 2026 12:00:00 +0900\n"
            "Message-ID: <original@example.com>\n"
        ),
        content_type="text/plain",
        parts=[MailBodyPart(guid="original/1", content="old\ntext")],
    )
    draft = SimpleNamespace(message=original)
    for name in ("create_draft", "create_reply_draft", "create_forward_draft"):
        getattr(service, name).return_value = draft
    monkeypatch.setattr(web_compose.web, "web_errors", nullcontext)
    monkeypatch.setattr(web_compose.web, "message", MagicMock(return_value=original))
    monkeypatch.setattr(web_compose.web, "display_name", lambda folder: folder.name)
    provider = ApiProvider(loader=lambda: SimpleNamespace(mail=service))
    return provider, service, draft


def test_send(mail, monkeypatch, tmp_path):
    provider, service, draft = mail
    path = tmp_path / "note.txt"
    path.write_bytes(b"hello")
    result = web_compose.send(
        provider,
        to=["Friend <friend@example.com>"],
        cc=["FRIEND@example.com"],
        subject="s",
        body="b",
        attachments=[str(path)],
    )
    service.upload_draft_attachment.assert_called_once_with(
        b"hello", filename="note.txt", content_type="text/plain"
    )
    service.create_draft.assert_called_once_with(
        sender="you@example.com",
        subject="s",
        text="b",
        to=("friend@example.com",),
        cc=("FRIEND@example.com",),
        bcc=(),
        attachments=(service.upload_draft_attachment.return_value,),
    )
    service.send_draft.assert_called_once_with(draft, confirm=True)
    assert result == {
        "sent": True,
        "message_id": "original",
        "from": "you@example.com",
        "recipients": ["friend@example.com"],
    }


@pytest.mark.parametrize(
    "address,env,ok",
    [
        (None, None, True),
        (None, "alias@example.com", True),
        ("ALIAS@example.com", None, True),
        ("unknown@example.com", None, False),
        ("disabled@example.com", None, False),
    ],
)
def test_sender(mail, monkeypatch, address, env, ok):
    provider, service, _ = mail
    service.senders.return_value.append(MailSender(address="alias@example.com"))
    monkeypatch.setenv("MCP_ICLOUD_MAIL_FROM_ALIASES", "alias@example.com,disabled@example.com")
    if env:
        monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", env)
    if ok:
        result = web_compose.send(
            provider, to=["friend@example.com"], subject="", body="", from_address=address
        )
        assert result["from"] == (address or env or "you@example.com")
    else:
        with pytest.raises(
            ToolError,
            match="enabled sender" if address.startswith("disabled") else "From must be one of",
        ):
            web_compose.send(
                provider, to=["friend@example.com"], subject="", body="", from_address=address
            )
        service.create_draft.assert_not_called()


@pytest.mark.parametrize("to", [[], ["bad"], [""]])
def test_recipients(mail, to):
    with pytest.raises(ToolError):
        web_compose.send(mail[0], to=to, subject="", body="")
    mail[1].create_draft.assert_not_called()


@pytest.mark.parametrize(
    "name,args",
    [
        ("send", {"to": ["friend@example.com"], "subject": "", "body": ""}),
        ("reply", {"mailbox": "INBOX", "uid": 1, "body": ""}),
        ("forward", {"mailbox": "INBOX", "uid": 1, "to": ["friend@example.com"]}),
    ],
)
def test_allowlist(mail, monkeypatch, name, args):
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", "@else.example.com")
    with pytest.raises(ToolError, match="Not sent: these recipients"):
        getattr(web_compose, name)(mail[0], **args)
    for method in ("create_draft", "create_reply_draft", "create_forward_draft", "send_draft"):
        getattr(mail[1], method).assert_not_called()


def test_rejected(mail):
    mail[1].send_draft.side_effect = MailWriteRejected("rejected")
    with pytest.raises(ToolError, match="left in Drafts"):
        web_compose.send(mail[0], to=["friend@example.com"], subject="", body="")


@pytest.mark.parametrize("reply_to", [False, True])
@pytest.mark.parametrize("plain", [False, True])
def test_reply(mail, monkeypatch, reply_to, plain):
    provider, service, draft = mail
    monkeypatch.setenv("MCP_ICLOUD_MAIL_FROM_ALIASES", "alias@example.com")
    body = service.body.return_value
    if reply_to:
        body = body.model_copy(update={"headers": body.headers + "Reply-To: reply@example.com\n"})
    if not plain:
        draft.message = draft.message.model_copy(
            update={"parts": [MailPart(id="2", content_type="text/html")]}
        )
        monkeypatch.setattr(web_compose.web, "message", lambda *args: draft.message)
    service.body.return_value = body
    result = web_compose.reply(provider, mailbox="INBOX", uid=1, body="answer", reply_all=True)
    kw = service.create_reply_draft.call_args.kwargs
    assert kw["to"] == (("reply@example.com",) if reply_to else ("friend@example.com",))
    assert kw["cc"] == ("other@example.com",)
    assert ("> old\n> text" in kw["text"]) is plain
    if not plain:
        assert kw["text"] == "answer"
    assert result["in_reply_to"] == "<original@example.com>"
    service.send_draft.assert_called_once_with(draft, confirm=True)


@pytest.mark.parametrize("include", [False, True])
def test_forward(mail, include):
    provider, service, draft = mail
    web_compose.forward(
        provider,
        mailbox="INBOX",
        uid=1,
        to=["friend@example.com"],
        body="intro",
        include_attachments=include,
    )
    kw = service.create_forward_draft.call_args.kwargs
    assert kw["include_original_attachments"] is include
    assert kw["text"] == (
        "intro\n\n---------- Forwarded message ----------\nFrom: friend@example.com\n"
        "Date: Fri, 27 Nov 2026 12:00:00 +0900\nSubject: Hello\n"
        "To: you@example.com, other@example.com\n\nold\ntext"
    )
    service.send_draft.assert_called_once_with(draft, confirm=True)


def test_draft(mail, monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", "@else.example.com")
    assert web_compose.save_draft(mail[0], to=["friend@example.com"]) == {
        "saved_as_draft": True,
        "mailbox": "Drafts",
        "message_id": "original",
    }
    mail[1].send_draft.assert_not_called()


@pytest.mark.anyio
async def test_dispatch(mail):
    async with Client(build_server(mail[0])) as client:
        for name, args in [
            ("send", {"to": ["friend@example.com"], "subject": "", "body": ""}),
            ("reply", {"mailbox": "INBOX", "uid": 1, "body": ""}),
            ("forward", {"mailbox": "INBOX", "uid": 1, "to": ["friend@example.com"]}),
            ("save_draft", {}),
        ]:
            assert not (await client.call_tool("mail_" + name, args)).is_error


def test_session(mail, tmp_path):
    def loader():
        raise NotLoggedInError(tmp_path)

    with pytest.raises(ToolError, match="mcp-icloud login"):
        web_compose.send(ApiProvider(loader=loader), to=["friend@example.com"], subject="", body="")


def test_reply_missing_id_and_own_only(mail):
    provider, service, _ = mail
    service.body.return_value = service.body.return_value.model_copy(
        update={"headers": "From: friend@example.com\n"}
    )
    assert web_compose.reply(provider, mailbox="INBOX", uid=1, body="")["in_reply_to"] is None
    service.create_reply_draft.reset_mock()
    service.body.return_value = service.body.return_value.model_copy(
        update={"headers": "From: you@example.com\n"}
    )
    with pytest.raises(ToolError, match="At least one recipient"):
        web_compose.reply(provider, mailbox="INBOX", uid=1, body="")
    service.create_reply_draft.assert_not_called()
