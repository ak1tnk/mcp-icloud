import json
import logging
import stat
from unittest.mock import MagicMock

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from pyicloud.exceptions import (
    PyiCloudAccountLockedException,
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudNoTrustedNumberAvailable,
    PyiCloudTrustedDevicePromptException,
    PyiCloudTrustedDeviceVerificationException,
)

from mcp_icloud import agent_login as login
from mcp_icloud import config
from mcp_icloud.server import ApiProvider, build_server
from mcp_icloud.session import NotLoggedInError


@pytest.fixture(autouse=True)
def setup(monkeypatch, session_dir):
    monkeypatch.setattr(login, "_pending", None)
    monkeypatch.setenv(config.APPLE_ID_ENV, " a@example.com ")
    monkeypatch.setenv(config.PASSWORD_ENV, " test-password ")
    monkeypatch.setattr(login, "monotonic", lambda: 100)
    monkeypatch.setattr(login, "load_api", MagicMock(side_effect=NotLoggedInError(session_dir)))
    api = MagicMock()
    api.requires_2fa = True
    api.requires_2sa = False
    api.is_trusted_session = True
    api.request_2fa_code.return_value = True
    api.validate_2fa_code.return_value = True
    api.two_factor_delivery_method = "trusted_device"
    api.two_factor_delivery_notice = None

    def construct(*args, **kwargs):
        (session_dir / "session-data").write_text("session data")
        (session_dir / "session-data").chmod(0o644)
        return api

    factory = MagicMock(side_effect=construct)
    monkeypatch.setattr(login, "PyiCloudService", factory)
    yield api, factory
    login._pending = None


def private(directory):
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in directory.iterdir())


@pytest.mark.anyio
async def test_happy_path(setup, session_dir):
    async with Client(build_server(ApiProvider(MagicMock()))) as client:
        tools = await client.list_tools()
        assert {"icloud_login_start", "icloud_login_verify"} <= {t.name for t in tools.tools}
        result = await client.call_tool("icloud_login_start")
        assert not result.is_error
        assert "code_sent" in str(result.content)
        private(session_dir)
        result = await client.call_tool("icloud_login_verify", {"code": "123456"})
        assert not result.is_error
        assert "logged_in" in str(result.content)
    assert json.loads((session_dir / "account.json").read_text()) == {"apple_id": "a@example.com"}
    private(session_dir)
    assert login._pending is None


def test_already_logged_in(setup, monkeypatch):
    api, factory = setup
    api.account_name = "stored@example.com"
    monkeypatch.setattr(login, "load_api", lambda: api)
    assert login.icloud_login_start() == {
        "status": "already_logged_in",
        "apple_id": "stored@example.com",
        "message": (
            "Already logged in as stored@example.com; nothing to do. The iCloud tools are ready."
        ),
    }
    factory.assert_not_called()


@pytest.mark.parametrize("name", [config.APPLE_ID_ENV, config.PASSWORD_ENV])
def test_missing_env(setup, monkeypatch, name):
    monkeypatch.setenv(name, " \t")
    with pytest.raises(ToolError) as caught:
        login.icloud_login_start()
    assert str(caught.value) == (
        "MCP_ICLOUD_APPLE_ID and MCP_ICLOUD_APPLE_PASSWORD must both be set in this MCP "
        "server's environment. Ask the user to add them as secrets/environment variables of "
        "this MCP server in the agent platform's connector settings (never in chat), restart "
        "or reconnect the server, then call icloud_login_start again. Without them, the user "
        "can run `mcp-icloud login` in a terminal instead."
    )
    setup[1].assert_not_called()
    login.load_api.assert_not_called()


@pytest.mark.parametrize("code", ["", "12345", "1234567", "１２３４５６", "abcdef"])
def test_bad_format(setup, code):
    login.icloud_login_start()
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify(code)
    assert str(caught.value) == (
        "The 2FA code must be 6 digits. Ask the user for the code shown on their device."
    )
    setup[0].validate_2fa_code.assert_not_called()
    assert login._pending.attempts == 0


def test_no_pending():
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify("123456")
    assert str(caught.value) == (
        "No login is in progress (or the server was restarted). Call icloud_login_start first."
    )


def test_expired(setup, monkeypatch):
    login.icloud_login_start()
    monkeypatch.setattr(login, "monotonic", lambda: 701)
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify("123456")
    assert str(caught.value) == (
        "The pending login expired after 10 minutes. Call icloud_login_start again "
        "to get a new code."
    )
    assert login._pending is None
    setup[0].validate_2fa_code.assert_not_called()


def test_wrong_then_right(setup):
    setup[0].validate_2fa_code.side_effect = [False, True]
    login.icloud_login_start()
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify("123456")
    assert str(caught.value) == (
        "Apple did not accept that code. Ask the user to check the code and call "
        "icloud_login_verify again, or call icloud_login_start for a new code."
    )
    assert login.icloud_login_verify(" 123 \t456\n")["status"] == "logged_in"
    setup[0].validate_2fa_code.assert_called_with("123456")


def test_three_wrong_codes(setup):
    setup[0].validate_2fa_code.return_value = False
    login.icloud_login_start()
    for _ in range(2):
        with pytest.raises(ToolError):
            login.icloud_login_verify("123456")
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify("123456")
    assert str(caught.value) == (
        "Apple did not accept the code 3 times. Call icloud_login_start again for a new code."
    )
    assert login._pending is None


@pytest.mark.parametrize(
    "error, message",
    [
        (
            PyiCloudAccountLockedException("bad", MagicMock()),
            "Apple reports this Apple ID as locked. Ask the user to unlock it at "
            "https://iforgot.apple.com. Do not call icloud_login_start again until the user "
            "confirms it is unlocked.",
        ),
        (
            PyiCloudFailedLoginException("bad"),
            "Apple rejected the Apple ID or password from MCP_ICLOUD_APPLE_ID / "
            "MCP_ICLOUD_APPLE_PASSWORD. Ask the user to correct the secret in the agent "
            "platform's settings (never in chat). Do not call icloud_login_start again until "
            "the user has fixed it: repeated failures can lock the Apple ID.",
        ),
        (
            PyiCloudNoTrustedNumberAvailable("bad"),
            "Two-factor authentication needs a trusted phone number, but Apple returned none.",
        ),
        (
            PyiCloudTrustedDevicePromptException("bad"),
            "Apple rejected the trusted-device 2FA step. Call icloud_login_start again.",
        ),
        (
            PyiCloudTrustedDeviceVerificationException("bad"),
            "Apple rejected the trusted-device 2FA step. Call icloud_login_start again.",
        ),
        (PyiCloudConnectionException("bad"), "Could not reach Apple. Check the network and retry."),
        (RuntimeError("bad"), "Login failed: RuntimeError."),
    ],
)
def test_start_errors(setup, error, message):
    setup[1].side_effect = error
    with pytest.raises(ToolError) as caught:
        login.icloud_login_start()
    assert str(caught.value) == message
    assert caught.value.__context__ is None
    assert login._pending is None


@pytest.mark.parametrize("security_key", [True, False])
def test_unsupported(setup, security_key):
    api, _ = setup
    if security_key:
        api.request_2fa_code.return_value = False
        message = (
            "This Apple ID needs a security key for two-factor authentication, which "
            "mcp-icloud does not support. Use an Apple ID with code-based 2FA."
        )
    else:
        api.requires_2fa = False
        api.requires_2sa = True
        message = (
            "This Apple ID uses legacy two-step verification, which is not supported. "
            "Ask the user to turn on two-factor authentication for the Apple ID."
        )
    with pytest.raises(ToolError) as caught:
        login.icloud_login_start()
    assert str(caught.value) == message
    assert login._pending is None
    assert "fido2_devices" not in str(api.mock_calls)


def test_fallback(setup):
    api, _ = setup
    api.request_2fa_code.side_effect = PyiCloudAPIResponseException("failed")
    api.two_factor_delivery_notice = "Use existing code"
    result = login.icloud_login_start()
    assert result["status"] == "code_sent"
    assert result["notice"] == "Use existing code"
    assert result["message"] == (
        "Apple could not send a new 2FA code. If a trusted Apple device of the user already "
        "shows a code, ask the user for it and call icloud_login_verify; otherwise call "
        "icloud_login_start again later."
    )
    api.use_existing_trusted_device_code.assert_called_once_with()


def test_verify_connection_keeps_pending(setup):
    api, _ = setup
    login.icloud_login_start()
    api.validate_2fa_code.side_effect = PyiCloudConnectionException("offline")
    with pytest.raises(ToolError, match="Could not reach Apple. Check the network and retry."):
        login.icloud_login_verify("123456")
    assert login._pending.attempts == 0
    api.validate_2fa_code.side_effect = None
    assert login.icloud_login_verify("123456")["status"] == "logged_in"


@pytest.mark.parametrize("stage", ["start", "verify"])
def test_password_never_leaks(setup, session_dir, caplog, stage):
    password = "test-password"
    caplog.set_level(logging.DEBUG)
    api, factory = setup
    results = []
    if stage == "start":
        factory.side_effect = PyiCloudFailedLoginException(f"bad {password}")
        call = login.icloud_login_start
    else:
        results.append(login.icloud_login_start())
        api.validate_2fa_code.side_effect = RuntimeError(password)

        def call():
            return login.icloud_login_verify("123456")

    with pytest.raises(ToolError) as caught:
        call()
    exc = caught.value
    while exc is not None:
        assert password not in str(exc)
        assert exc.__cause__ is None
        exc = exc.__context__
    assert password not in str(results)
    assert password not in caplog.text
    if session_dir.exists():
        assert all(password not in p.read_text() for p in session_dir.iterdir())
    assert login._pending is None


def test_without_2fa_and_trust(setup):
    api, _ = setup
    api.requires_2fa = False
    api.is_trusted_session = False
    api.trust_session.side_effect = lambda: setattr(api, "is_trusted_session", True)
    assert login.icloud_login_start()["status"] == "logged_in"
    api.trust_session.assert_called_once_with()


def test_untrusted_session(setup):
    api, _ = setup
    login.icloud_login_start()
    api.is_trusted_session = False
    with pytest.raises(ToolError) as caught:
        login.icloud_login_verify("123456")
    assert str(caught.value) == (
        "Apple accepted the code but did not trust this session. Call icloud_login_start again."
    )
    assert login._pending is None
