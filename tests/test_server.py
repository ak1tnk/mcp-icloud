from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from time import sleep
from unittest.mock import MagicMock

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudException,
)
from pyicloud.services.mail import MailWriteRejected, MailWriteUncertain

from mcp_icloud.server import ApiProvider, build_server
from mcp_icloud.session import NotLoggedInError


@pytest.mark.anyio
async def test_tools_and_lazy_build():
    loader = MagicMock()
    server = build_server(ApiProvider(loader))
    loader.assert_not_called()
    async with Client(server) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools if tool.name.startswith("hme_")} == {
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


def test_expired_cached_session_is_renewed_once():
    stale, fresh = MagicMock(), MagicMock()
    stale.hidemyemail.generate.side_effect = PyiCloudAPIResponseException("expired", 421)
    fresh.hidemyemail.generate.return_value = "new@example.com"
    loader = MagicMock(side_effect=[stale, fresh])
    provider = ApiProvider(loader)
    provider.call(lambda api: None)  # caches the stale session
    assert provider.call(lambda api: api.hidemyemail.generate()) == "new@example.com"
    assert loader.call_count == 2


def test_renewal_failure_reports_login(session_dir: Path):
    stale = MagicMock()
    stale.hidemyemail.generate.side_effect = PyiCloudAPIResponseException("expired", 421)
    loader = MagicMock(side_effect=[stale, NotLoggedInError(session_dir)])
    provider = ApiProvider(loader)
    provider.call(lambda api: None)
    with pytest.raises(ToolError, match="mcp-icloud login"):
        provider.call(lambda api: api.hidemyemail.generate())


@pytest.mark.parametrize(
    "exc",
    [
        PyiCloudConnectionException("timeout or connection reset"),  # no response: outcome unknown
        PyiCloudAPIResponseException("server error", 500),
        PyiCloudAPIResponseException("Authentication required for Account.", 500),
        PyiCloudAPIResponseException("unavailable", 503),
        MailWriteUncertain("submitted, outcome unknown"),  # pyicloud wraps any send-time failure
        MailWriteRejected("rejected"),
    ],
)
def test_no_retry_on_ambiguous_failures(exc):
    api = MagicMock()
    write = MagicMock(side_effect=exc)
    loader = MagicMock(return_value=api)
    provider = ApiProvider(loader)
    provider.call(lambda api: None)  # session cached, so a retry would be possible
    with pytest.raises(ToolError):
        provider.call(lambda api: write())
    assert write.call_count == 1
    assert loader.call_count == 1


@pytest.mark.anyio
async def test_hme_agent_login_guidance(monkeypatch, session_dir):
    monkeypatch.setenv("MCP_ICLOUD_APPLE_ID", "a@example.com")
    monkeypatch.setenv("MCP_ICLOUD_APPLE_PASSWORD", "example-password")
    loader = MagicMock(side_effect=NotLoggedInError(session_dir))
    async with Client(build_server(ApiProvider(loader))) as client:
        result = await client.call_tool("hme_generate")
        assert result.is_error
        assert "icloud_login_start" in str(result.content)
        assert "mcp-icloud login" in str(result.content)
