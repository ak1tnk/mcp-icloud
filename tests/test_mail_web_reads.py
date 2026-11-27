from contextlib import nullcontext
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.services.mail import MailBody, MailFolder, MailMessage, MailPart, MailSearchHit

from mcp_icloud.server import ApiProvider, build_server
from mcp_icloud.services.mail import web_reads
from mcp_icloud.session import NotLoggedInError


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_BACKEND", "auto")
    boxes = [
        MailFolder.model_validate({"identifier": name, "name": name, "uidValidity": 1})
        for name in ("INBOX", "Archive", "Deleted Messages")
    ]
    msg = MailMessage.model_validate(
        {
            "identifier": "message",
            "uid": 7,
            "mboxRef": {"id": "INBOX"},
            "folder": boxes[0],
            "from": "you@example.com",
            "stateInternalDate": 1795737600000,
            "parts": [
                {"partId": "1", "contentType": "text/html"},
                {"partId": "2", "contentType": "text/plain"},
                {"partId": "3", "attach": True, "fileName": "a.bin", "size": 3},
            ],
        }
    )
    api = MagicMock()
    service = api.mail
    service.folders.return_value = boxes
    service.message_by_uid.return_value = msg
    service.messages.return_value.messages = [msg]
    service.body.return_value = MailBody.model_validate(
        {
            "guid": "body",
            "longHeader": "Subject: header subject\r\nFrom: you@example.com\r\n"
            "Message-ID: <id@example.com>\r\n"
            "Date: Fri, 27 Nov 2026 12:00:00 +0900\r\nReply-To: you@example.com\r\n"
            "In-Reply-To: <previous@example.com>\r\nTo: you@example.com\r\nCc: you@example.com\r\n",
            "contentType": "multipart/mixed",
            "parts": [
                {"guid": "body-1", "content": "<p>HTML</p>"},
                {"guid": "body-2", "content": "plain text"},
            ],
        }
    )
    service.attachment.return_value = nullcontext(iter([b"abc"]))
    return ApiProvider(lambda: api), service, msg, boxes


@pytest.mark.anyio
async def test_eight_tools(setup, tmp_path):
    provider, service, msg, boxes = setup
    async with Client(build_server(provider)) as client:
        result = await client.call_tool("mail_list_mailboxes")
        assert result.structured_content == {
            "mailboxes": [
                {"name": b.name, "special_use": f"\\{flag}", "flags": []}
                for b, flag in zip(boxes, ("Inbox", "Archive", "Trash"), strict=True)
            ]
        }
        result = await client.call_tool("mail_search")
        assert result.structured_content == {
            "mailbox": "INBOX",
            "total_matches": 1,
            "messages": [
                {
                    "uid": 7,
                    "date": datetime.fromtimestamp(msg.internal_date / 1000, UTC).isoformat(),
                    "from": "you@example.com",
                    "to": None,
                    "cc": None,
                    "subject": "",
                    "size": 0,
                    "seen": None,
                    "flagged": None,
                }
            ],
        }
        result = await client.call_tool("mail_read", {"mailbox": "INBOX", "uid": 7, "max_chars": 5})
        data = result.structured_content
        assert data["text"] == "plain" and data["text_truncated"]
        assert data["subject"] == "header subject" and data["message_id"] == "<id@example.com>"
        assert data["date"] == "2026-11-27T12:00:00+09:00"
        assert data["attachments"] == [
            {"index": 0, "filename": "a.bin", "content_type": "application/octet-stream", "size": 3}
        ]
        service.set_read.assert_not_called()
        await client.call_tool("mail_read", {"mailbox": "INBOX", "uid": 7, "mark_read": True})
        service.set_read.assert_called_once_with(msg, read=True)
        target = tmp_path / "attachment"
        result = await client.call_tool(
            "mail_download_attachment",
            {"mailbox": "INBOX", "uid": 7, "index": 0, "path": str(target)},
        )
        assert result.structured_content["size"] == 3
        assert target.read_bytes() == b"abc" and target.stat().st_mode & 0o777 == 0o600
        result = await client.call_tool(
            "mail_set_flags", {"mailbox": "INBOX", "uids": [7], "seen": False, "flagged": True}
        )
        assert result.structured_content == {
            "mailbox": "INBOX",
            "uids": [7],
            "seen": False,
            "flagged": True,
        }
        service.set_flagged.assert_called_once_with(msg, flagged=True)
        for name, dest in (("move", boxes[1]), ("archive", boxes[1]), ("trash", boxes[2])):
            args = {"mailbox": "INBOX", "uids": [7]}
            if name == "move":
                args["destination"] = dest.name
            result = await client.call_tool("mail_" + name, args)
            assert result.structured_content == {
                "mailbox": "INBOX",
                "uids": [7],
                "destination": dest.name,
            }
            service.move.assert_called_with(msg, dest)
    service.delete_permanently.assert_not_called()


@pytest.mark.parametrize(
    "args",
    [
        {"sender": "a", "subject": "b"},
        {"subject": "日", "text": "本"},
        {"unread_only": True, "flagged_only": True},
        {"text": "a", "unread_only": True},
        {"text": "a", "flagged_only": True},
    ],
)
def test_limitations(setup, args):
    with pytest.raises(ToolError, match="mcp-icloud mail-login"):
        web_reads.search(setup[0], **args)
    setup[1].search.assert_not_called()


@pytest.mark.parametrize("mode", ["text", "unread", "flagged", "date", "cap"])
def test_search(setup, mode):
    provider, service, msg, _ = setup
    args = {"limit": 1}
    if mode == "text":
        service.search.return_value.results = [
            MailSearchHit.model_validate({"identifier": "thread"})
        ] * 2
        service.thread_messages.return_value.messages = [msg, msg.model_copy(update={"uid": 9})]
        args["sender"] = "you@example.com"
    elif mode in ("unread", "flagged"):
        service.iter_filtered_messages.return_value = iter([msg])
        args[mode + "_only"] = True
    else:
        args.update(since="2026-01-01", before="2027-01-01")
        values = (
            [msg.model_copy(update={"uid": i + 1}) for i in range(1005)]
            if mode == "cap"
            else [msg, msg.model_copy(update={"internal_date": 1})]
        )
        service.iter_messages.return_value = iter(values)
    data = web_reads.search(provider, **args)
    assert data["total_matches"] == (1000 if mode == "cap" else 2 if mode == "text" else 1)
    assert len(data["messages"]) == 1
    if mode == "unread":
        assert data["messages"][0]["seen"] is False
    if mode == "flagged":
        assert data["messages"][0]["flagged"] is True


@pytest.mark.parametrize(
    "mode,expected", [("html", "HTML"), ("none", ""), ("empty", ""), ("unknown", "first")]
)
def test_body(setup, mode, expected):
    provider, service, _, _ = setup
    body = service.body.return_value
    if mode == "none":
        service.body.side_effect = ValueError("Message has no supported text body parts")
    elif mode == "empty":
        service.body.return_value = body.model_copy(update={"parts": []})
    elif mode == "html":
        service.body.return_value = body.model_copy(update={"parts": body.parts[:1]})
    else:
        service.body.return_value = MailBody.model_validate(
            {
                "guid": "b",
                "longHeader": "",
                "contentType": "text/plain",
                "parts": [{"guid": "unknown", "content": "first"}],
            }
        )
    assert web_reads.read(provider, mailbox="INBOX", uid=7)["text"] == expected


@pytest.mark.parametrize(
    "mode", ["drop", "known", "stream", "existing", "relative", "parent", "index"]
)
def test_download(setup, tmp_path, monkeypatch, mode):
    provider, service, msg, _ = setup
    target = tmp_path / "file"
    if mode == "drop":
        msg.parts[-1] = MailPart.model_validate(
            {"partId": "3", "attach": True, "mailDropStreamingUrl": "https://example.com/fake"}
        )
        service.mail_drop_attachment.return_value = nullcontext(iter([b"abc"]))
    elif mode in ("known", "stream"):
        monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", "0.000001")
        if mode == "stream":
            msg.parts[-1] = msg.parts[-1].model_copy(update={"size": None})
    elif mode == "existing":
        target.write_bytes(b"keep")
    elif mode == "relative":
        target = type(target)("relative")
    elif mode == "parent":
        target = target / "missing" / "file"
    args = {
        "mailbox": "INBOX",
        "uid": 7,
        "index": 99 if mode == "index" else 0,
        "path": str(target),
    }
    if mode == "drop":
        assert web_reads.download_attachment(provider, **args)["size"] == 3
        service.mail_drop_attachment.assert_called_once_with(msg, 3, max_bytes=20 * 1024 * 1024)
    else:
        with pytest.raises(ToolError):
            web_reads.download_attachment(provider, **args)
        if mode == "existing":
            assert target.read_bytes() == b"keep"
        else:
            assert not target.exists()
        if mode == "known":
            service.attachment.assert_not_called()


@pytest.mark.anyio
async def test_session(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_BACKEND", "auto")

    def loader():
        raise NotLoggedInError(tmp_path)

    async with Client(build_server(ApiProvider(loader))) as client:
        result = await client.call_tool("mail_list_mailboxes")
        assert result.is_error and "mcp-icloud login" in str(result.content)


@pytest.mark.parametrize(
    "function,args,message",
    [
        ("search", {"limit": 0}, "limit must be 1 to 100"),
        ("search", {"since": "bad"}, "Dates must use YYYY-MM-DD"),
        ("search", {"before": "2026-02-30"}, "Dates must use YYYY-MM-DD"),
        ("read", {"mailbox": "INBOX", "uid": 0}, "uids must contain"),
        ("read", {"mailbox": "INBOX", "uid": 7, "max_chars": 0}, "max_chars must be"),
        ("set_flags", {"mailbox": "INBOX", "uids": []}, "uids must contain"),
        ("set_flags", {"mailbox": "INBOX", "uids": [7]}, "Provide seen or flagged"),
    ],
)
def test_validation(setup, function, args, message):
    with pytest.raises(ToolError, match=message):
        getattr(web_reads, function)(setup[0], **args)
    setup[1].message_by_uid.assert_not_called()


def test_date_boundaries(setup):
    provider, service, msg, _ = setup
    timestamp = datetime(2026, 11, 27, tzinfo=UTC).timestamp()
    service.iter_messages.return_value = iter(
        [
            msg.model_copy(update={"uid": 9, "internal_date": timestamp + 86400}),
            msg.model_copy(update={"uid": 8, "internal_date": timestamp}),
            msg.model_copy(update={"uid": 7, "internal_date": timestamp - 1}),
        ]
    )
    result = web_reads.search(provider, since="2026-11-27", before="2026-11-28")
    assert [m["uid"] for m in result["messages"]] == [8]


def test_stream_failure_removes_file(setup, tmp_path):
    from pyicloud.services.mail import MailError

    def chunks():
        yield b"a"
        raise MailError("fake stream failure")

    setup[1].attachment.return_value = nullcontext(chunks())
    target = tmp_path / "partial"
    with pytest.raises(ToolError, match="fake stream failure"):
        web_reads.download_attachment(setup[0], mailbox="INBOX", uid=7, index=0, path=str(target))
    assert not target.exists()
