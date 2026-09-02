import pytest

from domain.tools.services.tool_import_http_base import resolve_tool_import_base_url


@pytest.mark.parametrize(
    ("servers", "fetch", "want"),
    [
        (
            [{"url": "https://api.foo.com/v1"}],
            "http://ignored/openapi.json",
            "https://api.foo.com/v1",
        ),
        ([{"url": "https://api.foo.com"}], "http://ignored/openapi.json", "https://api.foo.com"),
        ([], "https://api.foo.com/openapi.json", "https://api.foo.com"),
        ([{"url": "/"}], "http://app:8088/openapi.json", "http://app:8088"),
    ],
)
def test_resolve_tool_import_base_url(servers, fetch, want) -> None:
    assert resolve_tool_import_base_url(openapi_servers=servers, openapi_fetch_url=fetch) == want


def test_the_default_base_url_is_used_when_the_spec_and_fetch_url_say_nothing() -> None:
    assert (
        resolve_tool_import_base_url(
            openapi_servers=[],
            openapi_fetch_url="file:///x.json",
            default_base_url="http://demo-api:8088",
        )
        == "http://demo-api:8088"
    )


def test_the_default_base_url_is_normalised() -> None:
    assert (
        resolve_tool_import_base_url(
            openapi_servers=[],
            openapi_fetch_url="file:///x.json",
            default_base_url="  http://demo-api:8088/  ",
        )
        == "http://demo-api:8088"
    )


def test_no_default_yields_an_empty_base_url_rather_than_a_hardcoded_host() -> None:
    assert (
        resolve_tool_import_base_url(openapi_servers=[], openapi_fetch_url="file:///x.json") == ""
    )


def test_the_spec_server_still_wins_over_the_default() -> None:
    assert (
        resolve_tool_import_base_url(
            openapi_servers=[{"url": "https://api.foo.com"}],
            openapi_fetch_url="file:///x.json",
            default_base_url="http://demo-api:8088",
        )
        == "https://api.foo.com"
    )
