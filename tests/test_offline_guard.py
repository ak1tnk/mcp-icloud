import pytest
import requests


def test_http_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is disabled"):
        requests.get("https://example.com", timeout=1)


def test_pyicloud_session_is_blocked(session_dir) -> None:
    from pyicloud import PyiCloudService

    api = PyiCloudService(
        "someone@example.com",
        password=None,
        cookie_directory=str(session_dir),
        authenticate=False,
    )
    with pytest.raises(Exception) as info:
        api.session.get("https://example.com")
    chain = []
    exc: BaseException | None = info.value
    while exc is not None:
        chain.append(str(exc))
        exc = exc.__cause__ or exc.__context__
    assert any("network access is disabled" in text for text in chain)
