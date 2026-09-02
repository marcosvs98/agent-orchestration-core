import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import api_documentation_urls

DOCUMENTATION_PATHS = ("/docs", "/redoc", "/openapi.json")


def _client(*, expose: bool) -> TestClient:
    docs_url, redoc_url, openapi_url = api_documentation_urls(expose=expose)
    return TestClient(FastAPI(docs_url=docs_url, redoc_url=redoc_url, openapi_url=openapi_url))


def test_open_when_exposed() -> None:
    assert api_documentation_urls(expose=True) == ("/docs", "/redoc", "/openapi.json")


def test_closed_when_not_exposed() -> None:
    assert api_documentation_urls(expose=False) == (None, None, None)


@pytest.mark.parametrize("path", DOCUMENTATION_PATHS)
def test_unauthenticated_request_is_refused_when_not_exposed(path: str) -> None:
    response = _client(expose=False).get(path)
    assert response.status_code != 200
    assert response.status_code == 404


@pytest.mark.parametrize("path", DOCUMENTATION_PATHS)
def test_unauthenticated_request_is_served_when_exposed(path: str) -> None:
    assert _client(expose=True).get(path).status_code == 200
