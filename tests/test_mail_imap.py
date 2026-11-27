from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_icloud.services.mail import imap
from mcp_icloud.services.mail.config import MailConfig


@pytest.mark.parametrize(
    "name,encoded",
    [
        ("~peter/mail/台北/日本語", "~peter/mail/&U,BTFw-/&ZeVnLIqe-"),
        ("&", "&-"),
        ("Inbox", "Inbox"),
        ("😀é&", "&2D3eAADp-&-"),
    ],
)
def test_encoding(name, encoded):
    assert imap.encode_mailbox_name(name) == encoded
    assert imap.decode_mailbox_name(encoded) == name


def test_list_and_special():
    conn = MagicMock()
    conn.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren \\Drafts) "/" "Drafts"',
            b'() "/" INBOX',
            (b'(\\Archive) "/" {5}', b"&U,BTFw-"),
            b'() "/" "a\\"b\\\\c"',
        ],
    )
    boxes = imap.list_mailboxes(conn)
    assert [b.name for b in boxes] == ["Drafts", "INBOX", "台北", 'a"b\\c']
    assert imap.special_mailbox(conn, "\\Archive", "Archive") == "台北"
    assert imap.special_mailbox(conn, "\\Trash", "INBOX") == "INBOX"
    with pytest.raises(ToolError):
        imap.special_mailbox(conn, "\\Trash", "missing")


@pytest.mark.parametrize("raises", [False, True])
def test_connect(raises):
    with patch.object(imap.imaplib, "IMAP4_SSL") as factory:
        conn = factory.return_value
        try:
            with imap.connect(MailConfig("you@example.com", "xxxx-xxxx-xxxx-xxxx")) as actual:
                assert actual is conn
                if raises:
                    raise ValueError("body")
        except ValueError:
            assert raises
        conn.login.assert_called_once_with("you@example.com", "xxxx-xxxx-xxxx-xxxx")
        conn.logout.assert_called_once()
        assert factory.call_args.kwargs["timeout"] == 30


def test_commands_and_failures():
    conn = MagicMock()
    conn.select.return_value = ("OK", [])
    imap.select(conn, "台北", readonly=True)
    conn.select.assert_called_with('"&U,BTFw-"', readonly=True)
    conn.uid.return_value = ("OK", [(b"1", b"Subject: hello\r\n\r\nbody")])
    assert imap.fetch_message(conn, 1)["Subject"] == "hello"
    conn.uid.assert_called_with("FETCH", "1", "(BODY.PEEK[])")
    conn.append.return_value = ("OK", [])
    imap.append(conn, "INBOX", "(\\Draft)", EmailMessage())
    assert conn.append.call_args.args[0] == '"INBOX"'
    conn.select.return_value = conn.uid.return_value = conn.append.return_value = ("NO", [])
    for action in (
        lambda: imap.select(conn, "x", readonly=True),
        lambda: imap.fetch_message(conn, 2),
        lambda: imap.append(conn, "x", "", EmailMessage()),
    ):
        with pytest.raises(ToolError):
            action()
