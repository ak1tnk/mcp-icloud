import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
)

from mcp_icloud import config, session


def test_missing_account(monkeypatch, session_dir):
    factory = Mock()
    monkeypatch.setattr(session, "PyiCloudService", factory)
    with pytest.raises(session.NotLoggedInError, match="mcp-icloud login"):
        session.load_api()
    factory.assert_not_called()
    assert not session_dir.exists()


@pytest.fixture
def api_setup(monkeypatch, session_dir):
    config.write_apple_id(session_dir, "a@example.com")
    api = SimpleNamespace(
        authenticate=Mock(), requires_2fa=False, requires_2sa=False, is_trusted_session=True
    )
    factory = Mock(return_value=api)
    monkeypatch.setattr(session, "PyiCloudService", factory)
    return api, factory


def test_success(api_setup, session_dir):
    api, factory = api_setup
    session_dir.chmod(0o755)
    assert session.load_api() is api
    factory.assert_called_once_with(
        "a@example.com", password=None, cookie_directory=str(session_dir), authenticate=False
    )
    api.authenticate.assert_called_once_with()
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700


@pytest.mark.parametrize("stage", ["constructor", "authenticate"])
@pytest.mark.parametrize(
    "error", [PyiCloudFailedLoginException("bad"), PyiCloudAPIResponseException("bad", 421)]
)
def test_auth_errors(api_setup, stage, error):
    api, factory = api_setup
    (factory if stage == "constructor" else api.authenticate).side_effect = error
    with pytest.raises(session.NotLoggedInError, match="mcp-icloud login") as caught:
        session.load_api()
    assert caught.value.__cause__ is error


@pytest.mark.parametrize("field", ["requires_2fa", "requires_2sa", "is_trusted_session"])
def test_untrusted(api_setup, field):
    api, _ = api_setup
    setattr(api, field, field != "is_trusted_session")
    with pytest.raises(session.NotLoggedInError):
        session.load_api()


@pytest.mark.parametrize("stage", ["constructor", "authenticate"])
@pytest.mark.parametrize("error", [PyiCloudConnectionException("offline"), ValueError("bad")])
def test_other_errors(api_setup, stage, error):
    api, factory = api_setup
    (factory if stage == "constructor" else api.authenticate).side_effect = error
    with pytest.raises(type(error)) as caught:
        session.load_api()
    assert caught.value is error
