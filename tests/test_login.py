import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudNoTrustedNumberAvailable,
    PyiCloudTrustedDevicePromptException,
    PyiCloudTrustedDeviceVerificationException,
)

from mcp_icloud import login
from mcp_icloud.session import NotLoggedInError


@pytest.fixture
def api_setup(monkeypatch):
    api = SimpleNamespace(
        requires_2fa=True,
        requires_2sa=False,
        fido2_devices=[],
        request_2fa_code=Mock(return_value=True),
        use_existing_trusted_device_code=Mock(),
        two_factor_delivery_notice="Code sent.",
        validate_2fa_code=Mock(side_effect=[False, True]),
        is_trusted_session=False,
        account_name="a@example.com",
    )
    api.trust_session = Mock(side_effect=lambda: setattr(api, "is_trusted_session", True))
    factory = Mock(return_value=api)
    monkeypatch.setattr(login, "PyiCloudService", factory)
    monkeypatch.setattr(login.getpass, "getpass", Mock(return_value="example-password"))
    monkeypatch.setattr("builtins.input", Mock(side_effect=[" bad ", " good "]))
    return api, factory


def test_happy_path(api_setup, session_dir, capsys):
    api, factory = api_setup
    assert login.login_command("a@example.com") == 0
    factory.assert_called_once_with(
        "a@example.com", "example-password", cookie_directory=str(session_dir)
    )
    assert api.validate_2fa_code.call_args_list == [(("bad",),), (("good",),)]
    api.trust_session.assert_called_once_with()
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700
    assert (session_dir / "account.json").exists()
    for file in session_dir.iterdir():
        assert stat.S_IMODE(file.stat().st_mode) == 0o600
        assert "example-password" not in file.read_text()
    captured = capsys.readouterr()
    assert "example-password" not in captured.out + captured.err
    assert "Code sent." in captured.out


def test_bad_codes(api_setup, monkeypatch, session_dir):
    api, _ = api_setup
    api.validate_2fa_code.side_effect = [False] * 3
    monkeypatch.setattr("builtins.input", Mock(return_value="bad"))
    assert login.login_command("a@example.com") == 1
    assert api.validate_2fa_code.call_count == 3
    assert not (session_dir / "account.json").exists()


@pytest.mark.parametrize("devices", [[], [object()]])
def test_security_key(api_setup, devices, capsys):
    api, _ = api_setup
    api.fido2_devices = devices
    api.request_2fa_code.return_value = False
    assert login.login_command("a@example.com") == 1
    assert "needs a security key" in capsys.readouterr().err
    api.validate_2fa_code.assert_not_called()


def test_legacy(api_setup, capsys):
    api, _ = api_setup
    api.requires_2fa = False
    api.requires_2sa = True
    assert login.login_command("a@example.com") == 1
    assert "Legacy two-step" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error",
    [PyiCloudFailedLoginException("example-password"), PyiCloudConnectionException("offline")],
)
def test_login_error(api_setup, error, capsys):
    _, factory = api_setup
    factory.side_effect = error
    assert login.login_command("a@example.com") == 1
    assert "example-password" not in capsys.readouterr().err


def test_empty_id(api_setup, monkeypatch):
    _, factory = api_setup
    monkeypatch.setattr("builtins.input", Mock(return_value="  "))
    assert login.login_command(None) == 2
    factory.assert_not_called()
    login.getpass.getpass.assert_not_called()


def test_status(monkeypatch, session_dir, capsys):
    monkeypatch.setattr(login, "load_api", Mock(return_value=SimpleNamespace(account_name="a")))
    assert login.status_command() == 0
    assert f"Session OK for a ({session_dir})" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["missing", "connection"])
def test_status_error(monkeypatch, session_dir, capsys, kind):
    error = NotLoggedInError(session_dir) if kind == "missing" else PyiCloudConnectionException("x")
    monkeypatch.setattr(login, "load_api", Mock(side_effect=error))
    assert login.status_command() == 1
    assert ("mcp-icloud login" if kind == "missing" else "Could not reach Apple") in (
        capsys.readouterr().err
    )


def test_logout(session_dir, capsys, monkeypatch):
    monkeypatch.setattr(login, "load_api", Mock(side_effect=NotLoggedInError(session_dir)))
    session_dir.mkdir()
    for name in ["account.json", "a.session", "a.cookiejar", "keep.txt", "a.session.bak"]:
        (session_dir / name).write_text("example")
    nested = session_dir / "nested.session"
    nested.mkdir()
    (nested / "a.cookiejar").write_text("keep")
    assert login.logout_command() == 0
    assert sorted(p.name for p in session_dir.iterdir()) == [
        "a.session.bak",
        "keep.txt",
        "nested.session",
    ]
    assert (nested / "a.cookiejar").exists()
    assert "Removed 3" in capsys.readouterr().out
    assert login.logout_command() == 0
    assert "Removed 0" in capsys.readouterr().out


def test_request_2fa_fallback(api_setup, capsys):
    api, _ = api_setup
    api.request_2fa_code.side_effect = PyiCloudAPIResponseException("x")
    assert login.login_command("a@example.com") == 0
    api.use_existing_trusted_device_code.assert_called_once_with()
    assert api.validate_2fa_code.call_count == 2
    assert (
        "Could not request a 2FA code. If a trusted Apple device already shows a code, "
        "enter it below."
    ) in capsys.readouterr().out


@pytest.mark.parametrize(
    "method,error,message",
    [
        (
            "request_2fa_code",
            PyiCloudConnectionException("x"),
            "Could not reach Apple. Check the network and retry.",
        ),
        (
            "request_2fa_code",
            PyiCloudNoTrustedNumberAvailable(),
            "Two-factor authentication needs a trusted phone number, but Apple returned none.",
        ),
        (
            "request_2fa_code",
            PyiCloudTrustedDevicePromptException("x"),
            "Apple rejected the trusted-device 2FA step. Retry `mcp-icloud login`.",
        ),
        (
            "validate_2fa_code",
            PyiCloudTrustedDeviceVerificationException("x"),
            "Apple rejected the trusted-device 2FA step. Retry `mcp-icloud login`.",
        ),
    ],
)
def test_2fa_errors(api_setup, session_dir, capsys, method, error, message):
    api, _ = api_setup
    getattr(api, method).side_effect = error
    assert login.login_command("a@example.com") == 1
    assert message in capsys.readouterr().err
    api.use_existing_trusted_device_code.assert_not_called()
    assert not (session_dir / "account.json").exists()


@pytest.mark.parametrize("outcome", ["confirmed", "unconfirmed", "missing", "connection"])
def test_remote_logout(monkeypatch, session_dir, capsys, outcome):
    session_dir.mkdir()
    for name in ["account.json", "a.session", "a.cookiejar"]:
        (session_dir / name).write_text("example")
    api = SimpleNamespace(
        logout=Mock(return_value={"remote_logout_confirmed": outcome == "confirmed"})
    )
    loader = Mock(return_value=api)
    if outcome == "missing":
        loader.side_effect = NotLoggedInError(session_dir)
    elif outcome == "connection":
        api.logout.side_effect = PyiCloudConnectionException("x")
    monkeypatch.setattr(login, "load_api", loader)
    assert login.logout_command() == 0
    loader.assert_called_once_with()
    if outcome != "missing":
        api.logout.assert_called_once_with()
    assert list(session_dir.iterdir()) == []
    output = capsys.readouterr().out
    assert "Removed 3 local session files." in output
    assert ("To revoke it at Apple" in output) == (outcome != "confirmed")
    assert {
        "confirmed": "Signed out of this session at Apple.",
        "unconfirmed": "Apple did not confirm the sign-out.",
        "missing": "No usable session; skipped signing out at Apple.",
        "connection": "Could not reach Apple; skipped signing out at Apple.",
    }[outcome] in output
