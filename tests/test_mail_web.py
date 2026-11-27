from unittest.mock import MagicMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.services.mail import MailError, MailFolder, MailWriteRejected, MailWriteUncertain

from mcp_icloud.services.mail import imap, web


@pytest.mark.parametrize(
    "name,flag",
    [
        ("INBOX", "Inbox"),
        ("Drafts", "Drafts"),
        ("Sent Messages", "Sent"),
        ("Deleted Messages", "Trash"),
        ("Junk", "Junk"),
        ("Archive", "Archive"),
        ("日本語", None),
    ],
)
def test_folders(name, flag):
    box = MailFolder.model_validate({"identifier": "box", "name": imap.encode_mailbox_name(name)})
    assert web.display_name(box) == name
    assert web.special_use(box) == ("\\" + flag if flag else None)
    service = MagicMock()
    service.folders.return_value = [box]
    assert web.folder(service, name) == box
    if flag:
        assert web.special_folder(service, flag.lower()) == box
    with pytest.raises(ToolError, match="not found"):
        web.folder(service, "missing")
    with pytest.raises(ToolError, match="not found"):
        web.special_folder(MagicMock(folders=lambda: []), "trash")
    service.message_by_uid.return_value = None
    with pytest.raises(ToolError, match="uid 1"):
        web.message(service, name, 1)


@pytest.mark.parametrize("error", [MailError, MailWriteRejected, ValueError, MailWriteUncertain])
def test_errors(error):
    with pytest.raises(ToolError) as caught, web.web_errors():
        raise error("fake")
    if error is MailWriteUncertain:
        assert "uncertain" in str(caught.value)
        assert "before any retry" in str(caught.value)
    else:
        assert "fake" in str(caught.value)


def test_passthrough():
    error = ToolError("fake")
    with pytest.raises(ToolError) as caught, web.web_errors():
        raise error
    assert caught.value is error
