import smtplib
from contextlib import nullcontext
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest
from mcp import Client

from mcp_icloud.server import build_server
from mcp_icloud.services.mail import compose

PASSWORD = "xxxx-xxxx-xxxx-xxxx"


@pytest.fixture
def mail(monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", "you@example.com")
    monkeypatch.setenv("MCP_ICLOUD_MAIL_APP_PASSWORD", PASSWORD)
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = smtp
    monkeypatch.setattr(compose.smtplib, "SMTP", smtp)
    original = EmailMessage()
    for key, value in {
        "From": "sender@example.org",
        "To": "you@example.com, other@example.org",
        "Cc": "alias@example.com, OTHER@example.org",
        "Subject": "Hello",
        "Date": "Fri, 27 Nov 2026 12:00:00 +0900",
        "Message-ID": "<original@example.org>",
        "References": "<older@example.org>",
    }.items():
        original[key] = value
    original.set_content("original\nsecond")
    conn = MagicMock()
    monkeypatch.setattr(compose.imap, "connect", MagicMock(return_value=nullcontext(conn)))
    monkeypatch.setattr(compose.imap, "select", MagicMock())
    monkeypatch.setattr(compose.imap, "fetch_message", MagicMock(return_value=original))
    monkeypatch.setattr(compose.imap, "special_mailbox", MagicMock(return_value="My Drafts"))
    monkeypatch.setattr(compose.imap, "append", MagicMock())
    return smtp, original, conn


async def invoke(tool, args):
    async with Client(build_server()) as client:
        return await client.call_tool(tool, args)


def sent(smtp):
    return smtp.send_message.call_args.args[0]


@pytest.mark.anyio
async def test_send(mail):
    smtp, _, _ = mail
    async with Client(build_server()) as client:
        tools = await client.list_tools()
        assert {"mail_send", "mail_reply", "mail_forward", "mail_save_draft"} <= {
            tool.name for tool in tools.tools
        }
        result = await client.call_tool(
            "mail_send",
            {
                "to": ["Friend <friend@example.org>"],
                "cc": ["FRIEND@example.org"],
                "bcc": ["hidden@example.net"],
                "subject": "こんにちは",
                "body": "本文",
            },
        )
    msg = sent(smtp)
    assert result.structured_content == {
        "sent": True,
        "message_id": msg["Message-ID"],
        "from": "you@example.com",
        "recipients": ["friend@example.org", "hidden@example.net"],
    }
    assert "@example.com>" in msg["Message-ID"]
    assert msg["Bcc"] is None and msg["To"] == "friend@example.org"
    assert msg["Cc"] == "FRIEND@example.org" and msg["Date"]
    assert msg["Subject"] == "こんにちは" and msg.get_content() == "本文\n"
    assert msg.get_content_charset() == "utf-8"
    smtp.assert_called_once_with("smtp.mail.me.com", 587, timeout=30)
    names = [c[0] for c in smtp.mock_calls]
    assert names.index("starttls") < names.index("login") < names.index("send_message")
    assert smtp.starttls.call_args.kwargs["context"]
    smtp.login.assert_called_once_with("you@example.com", PASSWORD)
    assert smtp.send_message.call_args.kwargs == {
        "from_addr": "you@example.com",
        "to_addrs": ["friend@example.org", "hidden@example.net"],
    }


@pytest.mark.anyio
@pytest.mark.parametrize("recipients", [[], ["bad"], [""], ["valid@example.org", "bad"]])
async def test_bad_recipients(mail, recipients):
    result = await invoke("mail_send", {"to": recipients, "subject": "s", "body": "b"})
    assert result.is_error
    mail[0].assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "allowlist,recipient,ok",
    [
        ("", "any@example.net", True),
        ("friend@example.org", "FRIEND@example.org", True),
        ("@example.org", "a@example.org", True),
        ("@example.org", "a@badexample.test", False),
        ("friend@example.org", "other@example.org", False),
    ],
)
async def test_allowlist(mail, monkeypatch, allowlist, recipient, ok):
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", allowlist)
    result = await invoke("mail_send", {"to": [recipient], "subject": "s", "body": "b"})
    assert result.is_error is not ok
    if not ok:
        assert "Not sent: these recipients are not on MCP_ICLOUD_SEND_ALLOWLIST: " in str(
            result.content
        )
        mail[0].assert_not_called()
        compose.imap.append.assert_not_called()


TOOLS = [
    ("mail_send", {"to": ["a@example.org"], "subject": "s", "body": "b"}),
    ("mail_reply", {"mailbox": "INBOX", "uid": 1, "body": "b"}),
    ("mail_forward", {"mailbox": "INBOX", "uid": 1, "to": ["a@example.org"]}),
    ("mail_save_draft", {}),
]


@pytest.mark.anyio
@pytest.mark.parametrize("tool,args", TOOLS)
@pytest.mark.parametrize("allowed", [True, False])
async def test_from(mail, monkeypatch, tool, args, allowed):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_FROM_ALIASES", "alias@example.com")
    result = await invoke(
        tool, {**args, "from_address": "ALIAS@example.com" if allowed else "unknown@example.com"}
    )
    assert result.is_error is not allowed
    if not allowed:
        assert "you@example.com, alias@example.com" in str(result.content)
        mail[0].assert_not_called()
        compose.imap.connect.assert_not_called()


@pytest.mark.anyio
async def test_attachments(mail, tmp_path, monkeypatch):
    path = tmp_path / "note.txt"
    path.write_bytes(b"contents")
    args = {"to": ["a@example.org"], "subject": "s", "body": "b"}
    assert not (await invoke("mail_send", {**args, "attachments": [str(path)]})).is_error
    part = next(sent(mail[0]).iter_attachments())
    assert part.get_filename() == "note.txt" and part.get_content_type() == "text/plain"
    assert part.get_payload(decode=True) == b"contents"
    for paths in [["relative.txt"], [str(tmp_path / "missing")], [str(tmp_path)]]:
        mail[0].reset_mock()
        assert (await invoke("mail_send", {**args, "attachments": paths})).is_error
        mail[0].assert_not_called()
    monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", str(10 / 1024 / 1024))
    mail[0].reset_mock()
    assert (await invoke("mail_send", {**args, "attachments": [str(path), str(path)]})).is_error
    mail[0].assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("reply_to", [False, True])
async def test_reply(mail, monkeypatch, reply_to):
    smtp, original, conn = mail
    monkeypatch.setenv("MCP_ICLOUD_MAIL_FROM_ALIASES", "alias@example.com")
    if reply_to:
        original["Reply-To"] = "reply@example.org"
        original.replace_header("Subject", "rE: Hello")
    result = await invoke(
        "mail_reply", {"mailbox": "INBOX", "uid": 42, "body": "answer", "reply_all": True}
    )
    assert not result.is_error
    msg = sent(smtp)
    assert msg["To"] == ("reply@example.org" if reply_to else "sender@example.org")
    assert msg["Cc"] == "other@example.org"
    assert msg["Subject"] == ("rE: Hello" if reply_to else "Re: Hello")
    assert msg["In-Reply-To"] == "<original@example.org>"
    assert msg["References"] == "<older@example.org> <original@example.org>"
    assert "answer\n\nOn " in msg.get_content()
    assert "sender@example.org wrote:\n> original\n> second" in msg.get_content()
    compose.imap.select.assert_called_once_with(conn, "INBOX", readonly=True)
    compose.imap.fetch_message.assert_called_once_with(conn, 42)


@pytest.mark.anyio
@pytest.mark.parametrize("include", [True, False])
@pytest.mark.parametrize("subject", ["Hello", "Fw: Hello", "fWd: Hello"])
async def test_forward(mail, include, subject):
    smtp, original, _ = mail
    original.replace_header("Subject", subject)
    original.add_attachment(
        b"data", maintype="application", subtype="octet-stream", filename="a.bin"
    )
    result = await invoke(
        "mail_forward",
        {
            "mailbox": "INBOX",
            "uid": 1,
            "to": ["a@example.org"],
            "body": "intro",
            "include_attachments": include,
        },
    )
    assert not result.is_error
    msg = sent(smtp)
    assert msg["Subject"] == ("Fwd: Hello" if subject == "Hello" else subject)
    text = msg.get_body(preferencelist=("plain",)).get_content()
    assert "intro\n\n---------- Forwarded message ----------\nFrom: sender@example.org\n" in text
    assert f"Subject: {subject}\nTo: you@example.com, other@example.org\n\noriginal" in text
    parts = list(msg.iter_attachments())
    assert len(parts) == int(include)
    if include:
        assert parts[0].get_payload(decode=True) == b"data"
        assert parts[0].get_filename() == "a.bin"


@pytest.mark.anyio
async def test_draft(mail, monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", "@blocked.org")
    result = await invoke("mail_save_draft", {"to": ["a@example.org"], "bcc": ["b@example.org"]})
    assert not result.is_error
    smtp, _, conn = mail
    smtp.assert_not_called()
    compose.imap.special_mailbox.assert_called_once_with(conn, "\\Drafts", "Drafts")
    args = compose.imap.append.call_args.args
    assert args[:3] == (conn, "My Drafts", "(\\Draft \\Seen)")
    assert args[3]["Bcc"] is None
    assert result.structured_content == {
        "saved_as_draft": True,
        "mailbox": "My Drafts",
        "message_id": args[3]["Message-ID"],
    }


@pytest.mark.anyio
async def test_auth_error(mail):
    mail[0].login.side_effect = smtplib.SMTPAuthenticationError(535, PASSWORD.encode())
    result = await invoke("mail_send", TOOLS[0][1])
    assert result.is_error and "SMTP" in str(result.content)
    assert PASSWORD not in str(result.content)
    mail[0].send_message.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("tool,args", TOOLS)
async def test_not_configured(tool, args):
    result = await invoke(tool, args)
    assert result.is_error
    assert "iCloud Mail is not configured" in str(result.content)


@pytest.mark.anyio
async def test_reply_without_plain_text_and_empty_recipients(mail):
    smtp, original, _ = mail
    original.set_content("<p>html</p>", subtype="html")
    result = await invoke("mail_reply", {"mailbox": "INBOX", "uid": 1, "body": "answer"})
    assert not result.is_error
    assert sent(smtp).get_content() == "answer\n"
    original.replace_header("From", "you@example.com")
    smtp.reset_mock()
    result = await invoke("mail_reply", {"mailbox": "INBOX", "uid": 1, "body": "answer"})
    assert result.is_error
    smtp.assert_not_called()


@pytest.mark.anyio
async def test_forward_limit_and_allowlist(mail, monkeypatch):
    smtp, original, _ = mail
    original.add_attachment(b"large", maintype="application", subtype="octet-stream")
    args = {"mailbox": "INBOX", "uid": 1, "to": ["a@example.org"]}
    monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", "0")
    assert (await invoke("mail_forward", args)).is_error
    smtp.assert_not_called()
    monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", "20")
    monkeypatch.setenv("MCP_ICLOUD_SEND_ALLOWLIST", "@else.org")
    for tool, values in [
        ("mail_forward", args),
        ("mail_reply", {"mailbox": "INBOX", "uid": 1, "body": "b"}),
    ]:
        result = await invoke(tool, values)
        assert result.is_error
        assert "Not sent: these recipients" in str(result.content)
    smtp.assert_not_called()
    compose.imap.append.assert_not_called()
