import os
from email.message import EmailMessage
from unittest.mock import patch

import pytest
from mcp import Client

from mcp_icloud.server import build_server


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("MCP_ICLOUD_MAIL_USER", "you@example.com")
    monkeypatch.setenv("MCP_ICLOUD_MAIL_APP_PASSWORD", "xxxx-xxxx-xxxx-xxxx")
    with patch("mcp_icloud.services.mail.imap.imaplib.IMAP4_SSL") as factory:
        conn = factory.return_value
        conn.list.return_value = (
            "OK",
            [b'() "/" INBOX', b'(\\Archive) "/" Archive', b'(\\Trash) "/" "Deleted Messages"'],
        )
        conn.select.return_value = ("OK", [])
        conn.uid.return_value = ("OK", [])
        conn.capabilities = (b"MOVE",)
        yield conn


def message():
    msg = EmailMessage()
    msg["From"] = "you@example.com"
    msg["Subject"] = "日本語"
    msg.set_content("<p>Hello</p><script>hidden</script><div>world</div>", subtype="html")
    msg.add_attachment(b"abc", maintype="application", subtype="octet-stream", filename="a.bin")
    return msg.as_bytes()


@pytest.mark.anyio
async def test_tools(conn, tmp_path):
    async with Client(build_server()) as client:
        result = await client.call_tool("mail_list_mailboxes")
        assert result.structured_content["mailboxes"][0]["special_use"] == "\\Inbox"
        conn.uid.return_value = ("OK", [(b"1", message())])
        result = await client.call_tool("mail_read", {"mailbox": "INBOX", "uid": 1, "max_chars": 3})
        data = result.structured_content
        assert data["text"] == "Hel" and data["text_truncated"]
        assert data["attachments"][0]["size"] == 3
        assert "xxxx-xxxx-xxxx-xxxx" not in str(data)
        assert all(c.args[0] != "STORE" for c in conn.uid.call_args_list)
        await client.call_tool("mail_read", {"mailbox": "INBOX", "uid": 1, "mark_read": True})
        conn.uid.assert_called_with("STORE", "1", "+FLAGS", "(\\Seen)")
        target = tmp_path / "a.bin"
        result = await client.call_tool(
            "mail_download_attachment",
            {"mailbox": "INBOX", "uid": 1, "index": 0, "path": str(target)},
        )
        assert not result.is_error
        assert target.read_bytes() == b"abc"
        assert os.stat(target).st_mode & 0o777 == 0o600
        conn.uid.return_value = ("OK", [])
        await client.call_tool(
            "mail_set_flags", {"mailbox": "INBOX", "uids": [1], "seen": False, "flagged": True}
        )
        conn.uid.assert_called_with("STORE", "1", "+FLAGS", "(\\Flagged)")
        for tool, destination in [
            ("mail_move", "Archive"),
            ("mail_archive", "Archive"),
            ("mail_trash", "Deleted Messages"),
        ]:
            args = {"mailbox": "INBOX", "uids": [1]}
            if tool == "mail_move":
                args["destination"] = destination
            result = await client.call_tool(tool, args)
            assert result.structured_content["destination"] == destination
            conn.uid.assert_called_with("MOVE", "1", f'"{destination}"')
        assert all(c.args[0] not in ("EXPUNGE",) for c in conn.uid.call_args_list)


@pytest.mark.anyio
async def test_search(conn):
    async with Client(build_server()) as client:
        conn.uid.side_effect = [
            ("OK", [b"1 9 3"]),
            (
                "OK",
                [
                    (
                        b"1 (UID 9 FLAGS (\\Seen \\Flagged) RFC822.SIZE 55)",
                        b"Subject: =?utf-8?b?5pel5pys6Kqe?=\r\n"
                        b"Date: Fri, 27 Nov 2026 12:00:00 +0900\r\n\r\n",
                    )
                ],
            ),
        ]
        result = await client.call_tool(
            "mail_search",
            {
                "sender": "you@example.com",
                "since": "2026-01-02",
                "before": "2026-12-01",
                "unread_only": True,
                "flagged_only": True,
                "limit": 1,
            },
        )
        assert result.structured_content["total_matches"] == 3
        assert result.structured_content["messages"][0]["subject"] == "日本語"
        assert conn.uid.call_args_list[0].args == (
            "SEARCH",
            "FROM",
            '"you@example.com"',
            "SINCE",
            "02-Jan-2026",
            "BEFORE",
            "01-Dec-2026",
            "UNSEEN",
            "FLAGGED",
        )
        assert conn.uid.call_args.args[1] == "9"
        conn.uid.side_effect = None
        conn.uid.return_value = ("OK", [b""])
        await client.call_tool("mail_search")
        conn.uid.assert_called_with("SEARCH", "ALL")
        await client.call_tool("mail_search", {"subject": "日本語"})
        conn.uid.assert_called_with("SEARCH", "CHARSET", "UTF-8", "SUBJECT")
        assert conn.literal == "日本語".encode()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool,args",
    [
        ("mail_search", {"subject": "日", "text": "本"}),
        ("mail_search", {"since": "bad"}),
        ("mail_search", {"limit": 0}),
        ("mail_read", {"mailbox": "INBOX", "uid": 0}),
        ("mail_read", {"mailbox": "INBOX", "uid": 1, "max_chars": 0}),
        ("mail_set_flags", {"mailbox": "INBOX", "uids": []}),
        ("mail_set_flags", {"mailbox": "INBOX", "uids": [1]}),
        ("mail_move", {"mailbox": "INBOX", "uids": [1], "destination": "missing"}),
        (
            "mail_download_attachment",
            {"mailbox": "INBOX", "uid": 1, "index": 0, "path": "relative"},
        ),
    ],
)
async def test_validation(conn, tool, args):
    async with Client(build_server()) as client:
        result = await client.call_tool(tool, args)
        assert result.is_error


@pytest.mark.anyio
async def test_move_capability_and_missing_config(conn, monkeypatch):
    conn.capabilities = ()
    async with Client(build_server()) as client:
        result = await client.call_tool(
            "mail_move", {"mailbox": "INBOX", "uids": [1], "destination": "Archive"}
        )
        assert result.is_error and "MOVE" in str(result.content)
        monkeypatch.delenv("MCP_ICLOUD_MAIL_APP_PASSWORD")
        monkeypatch.setenv("MCP_ICLOUD_MAIL_BACKEND", "imap")
        result = await client.call_tool("mail_list_mailboxes")
        assert result.is_error and "MCP_ICLOUD_MAIL_APP_PASSWORD" in str(result.content)


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["existing", "parent", "large", "index"])
async def test_download_errors(conn, tmp_path, monkeypatch, case):
    conn.uid.return_value = ("OK", [(b"1", message())])
    target = tmp_path / "file"
    if case == "existing":
        target.write_bytes(b"keep")
    elif case == "parent":
        target = tmp_path / "missing" / "file"
    elif case == "large":
        monkeypatch.setenv("MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB", "0")
    async with Client(build_server()) as client:
        result = await client.call_tool(
            "mail_download_attachment",
            {
                "mailbox": "INBOX",
                "uid": 1,
                "index": 5 if case == "index" else 0,
                "path": str(target),
            },
        )
        assert result.is_error
    if case == "existing":
        assert target.read_bytes() == b"keep"
    else:
        assert not target.exists()


@pytest.mark.anyio
@pytest.mark.parametrize("uids", [[0], [-1], list(range(1, 502))])
async def test_uid_validation(conn, uids):
    async with Client(build_server()) as client:
        result = await client.call_tool(
            "mail_set_flags", {"mailbox": "INBOX", "uids": uids, "seen": True}
        )
        assert result.is_error
