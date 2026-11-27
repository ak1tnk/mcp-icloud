from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from time import sleep
from unittest.mock import MagicMock

import pytest
from mcp import Client
from pyicloud.exceptions import PyiCloudAPIResponseException, PyiCloudException

from mcp_icloud.server import ApiProvider, build_server
from mcp_icloud.session import NotLoggedInError


@pytest.mark.anyio
async def test_tools_and_lazy_build():
    loader = MagicMock()
    server = build_server(ApiProvider(loader))
    loader.assert_not_called()
    async with Client(server) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "hme_list",
            "hme_generate",
            "hme_reserve",
            "hme_update",
            "hme_deactivate",
            "hme_reactivate",
        }
    loader.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("during_call", [False, True])
async def test_auth_errors_reload(during_call, session_dir: Path):
    api = MagicMock()
    if during_call:
        api.hidemyemail.generate.side_effect = PyiCloudAPIResponseException("expired", 421)
        loader = MagicMock(return_value=api)
    else:
        loader = MagicMock(side_effect=NotLoggedInError(session_dir))
    async with Client(build_server(ApiProvider(loader))) as client:
        for _ in range(2):
            result = await client.call_tool("hme_generate")
            assert result.is_error
            assert "mcp-icloud login" in str(result.content)
    assert loader.call_count == 2


@pytest.mark.anyio
async def test_request_error():
    api = MagicMock()
    api.hidemyemail.generate.side_effect = PyiCloudException("failed")
    async with Client(build_server(ApiProvider(lambda: api))) as client:
        result = await client.call_tool("hme_generate")
        assert result.is_error
        assert "iCloud request failed: PyiCloudException: failed" in str(result.content)


def test_other_exception_propagates():
    loader = MagicMock(side_effect=ValueError("unexpected"))
    with pytest.raises(ValueError, match="unexpected"):
        ApiProvider(loader).call(lambda api: api)


def test_concurrent_calls_share_serialized_session():
    api = object()
    active = 0
    barrier = Barrier(2)

    def load():
        sleep(0.03)
        return api

    loader = MagicMock(side_effect=load)
    provider = ApiProvider(loader)

    def use_session(session):
        nonlocal active
        assert session is api
        active += 1
        assert active == 1
        sleep(0.03)
        active -= 1
        return "ok"

    def call():
        barrier.wait(timeout=5)
        return provider.call(use_session)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(call) for _ in range(2)]
        assert [future.result(timeout=5) for future in futures] == ["ok", "ok"]
    loader.assert_called_once_with()
