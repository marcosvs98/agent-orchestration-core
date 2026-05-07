import pytest

from domain.tools.services.tool_import_http_base import resolve_tool_import_base_url


@pytest.mark.parametrize(
    ("servers", "fetch", "want"),
    [
        ([{"url": "https://api.foo.com/v1"}], "http://ignored/openapi.json", "https://api.foo.com/v1"),
        ([{"url": "https://api.foo.com"}], "http://ignored/openapi.json", "https://api.foo.com"),
        ([], "https://api.foo.com/openapi.json", "https://api.foo.com"),
        ([{"url": "/"}], "http://app:8088/openapi.json", "http://app:8088"),
    ],
)
def test_resolve_tool_import_base_url(servers, fetch, want) -> None:
    assert resolve_tool_import_base_url(openapi_servers=servers, openapi_fetch_url=fetch) == want


def test_resolve_tool_import_base_url_env_fallback(monkeypatch) -> None:
    monkeypatch.delenv("UORA_APP_PLATFORM_HTTP_BASE", raising=False)
    assert (
        resolve_tool_import_base_url(openapi_servers=[], openapi_fetch_url="file:///x.json")
        == "http://host.docker.internal:8088"
    )


def test_resolve_tool_import_base_url_env_override(monkeypatch) -> None:
    monkeypatch.setenv("UORA_APP_PLATFORM_HTTP_BASE", "http://custom:9999")
    assert (
        resolve_tool_import_base_url(openapi_servers=[], openapi_fetch_url="file:///x.json")
        == "http://custom:9999"
    )
