from unittest.mock import MagicMock

import pytest
from mcp import Client

from mcp_icloud.server import ApiProvider, build_server

RAW = {
    "hme": "alias@example.com",
    "anonymousId": "id",
    "label": "old",
    "note": "memo",
    "isActive": True,
    "forwardToEmail": "owner@example.com",
    "domain": "icloud.com",
    "createTimestamp": 0,
}
ALIAS = {
    "email": "alias@example.com",
    "anonymous_id": "id",
    "label": "old",
    "note": "memo",
    "active": True,
    "forward_to": "owner@example.com",
    "domain": "icloud.com",
    "created_at": "1970-01-01T00:00:00+00:00",
}


@pytest.fixture
def api():
    api = MagicMock()
    api.hidemyemail.__iter__.return_value = iter([RAW, {**RAW, "isActive": False}])
    api.hidemyemail.generate.return_value = RAW["hme"]
    api.hidemyemail.reserve.return_value = {"hme": RAW}
    api.hidemyemail.__getitem__.return_value = {"hme": RAW}
    return api


@pytest.mark.anyio
async def test_happy_paths(api):
    loader = MagicMock(return_value=api)
    async with Client(build_server(ApiProvider(loader))) as client:
        result = await client.call_tool("hme_list")
        assert result.structured_content == {
            "count": 2,
            "addresses": [ALIAS, {**ALIAS, "active": False}],
        }
        result = await client.call_tool("hme_generate")
        assert result.structured_content == {"email": RAW["hme"]}
        result = await client.call_tool("hme_reserve", {"email": " x ", "label": " y "})
        assert result.structured_content == ALIAS
        api.hidemyemail.reserve.assert_called_once_with("x", "y", "")
        for tool, active in [("hme_deactivate", False), ("hme_reactivate", True)]:
            api.hidemyemail.__getitem__.return_value = {**RAW, "isActive": active}
            getattr(api.hidemyemail, tool.removeprefix("hme_")).return_value = {}
            result = await client.call_tool(tool, {"anonymous_id": " id "})
            assert result.structured_content == {**ALIAS, "active": active}
            getattr(api.hidemyemail, tool.removeprefix("hme_")).assert_called_once_with("id")
    loader.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "args,expected",
    [
        ({"label": "new"}, ("id", "new", "memo")),
        ({"note": "new"}, ("id", "old", "new")),
        ({"note": ""}, ("id", "old", "")),
    ],
)
async def test_update(api, args, expected):
    changed = {**RAW, **args}
    api.hidemyemail.__getitem__.side_effect = [{"hme": RAW}, {"hme": changed}]
    async with Client(build_server(ApiProvider(lambda: api))) as client:
        result = await client.call_tool("hme_update", {"anonymous_id": " id ", **args})
        assert not result.is_error
        assert result.structured_content == {**ALIAS, **args}
    api.hidemyemail.update_metadata.assert_called_once_with(*expected)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool,args,setup,message",
    [
        ("hme_generate", {}, "generate", "did not generate"),
        ("hme_reserve", {"email": "x", "label": "y"}, "reserve", "did not reserve"),
        ("hme_update", {"anonymous_id": "id"}, "", "Provide label or note"),
        ("hme_update", {"anonymous_id": "id", "note": "x"}, "get", "alias not found"),
        ("hme_update", {"anonymous_id": "id", "note": "x"}, "update_metadata", "did not confirm"),
        ("hme_deactivate", {"anonymous_id": "id"}, "", "did not confirm"),
        ("hme_reactivate", {"anonymous_id": "id"}, "inactive", "did not confirm"),
        ("hme_deactivate", {"anonymous_id": "id"}, "get", "alias not found"),
        ("hme_reactivate", {"anonymous_id": "id"}, "get", "alias not found"),
    ],
)
async def test_failures(api, tool, args, setup, message):
    if setup == "get":
        api.hidemyemail.__getitem__.return_value = {}
    elif setup == "inactive":
        api.hidemyemail.__getitem__.return_value = {**RAW, "isActive": False}
    elif setup:
        getattr(api.hidemyemail, setup).return_value = None if setup == "generate" else {}
    async with Client(build_server(ApiProvider(lambda: api))) as client:
        result = await client.call_tool(tool, args)
        assert result.is_error
        assert message in str(result.content)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool,args",
    [
        ("hme_reserve", {"email": " ", "label": "x"}),
        ("hme_reserve", {"email": "x", "label": " "}),
        ("hme_update", {"anonymous_id": " ", "note": "x"}),
        ("hme_deactivate", {"anonymous_id": " "}),
        ("hme_reactivate", {"anonymous_id": " "}),
    ],
)
async def test_empty_required(api, tool, args):
    loader = MagicMock(return_value=api)
    async with Client(build_server(ApiProvider(loader))) as client:
        result = await client.call_tool(tool, args)
        assert result.is_error
        assert "must not be empty" in str(result.content)
    loader.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("timestamp", [None, "0", 0.5, True])
async def test_missing_fields_and_timestamp(api, timestamp):
    api.hidemyemail.reserve.return_value = {"createTimestamp": timestamp}
    async with Client(build_server(ApiProvider(lambda: api))) as client:
        result = await client.call_tool("hme_reserve", {"email": "x", "label": "y"})
        assert result.structured_content == dict.fromkeys(ALIAS)
