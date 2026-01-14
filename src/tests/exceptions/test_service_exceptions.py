import pytest
from starlette.requests import Request

from exceptions.service_exceptions import (
    MethodNotAllowedPlaceholderException,
    router_http_exception_handler,
)


@pytest.mark.asyncio
async def test_method_not_allowed_placeholder_exception_status_and_body():
    exc = MethodNotAllowedPlaceholderException()
    scope = {"type": "http", "method": "GET", "path": "/core/v1/placeholder", "headers": []}
    request = Request(scope)

    response = await router_http_exception_handler(request, exc)

    assert response.status_code == 405
    body = response.body.decode()
    assert "METHOD_NOT_ALLOWED" in body
    assert "Endpoint not available." in body
