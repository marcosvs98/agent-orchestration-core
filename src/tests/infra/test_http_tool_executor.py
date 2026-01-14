import httpx
import pytest

from infra.http_tool_executor import HttpToolExecutor


class TestHttpToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_http_returns_status_headers_text(self, monkeypatch):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"x-test": "1"}, text="ok")

        transport = httpx.MockTransport(handler)

        original_client = httpx.AsyncClient

        class PatchedAsyncClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, transport=transport, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)

        executor = HttpToolExecutor()
        result = await executor.execute_http(
            method="POST",
            url="https://example.com",
            headers={},
            json_body={"a": 1},
            timeout_seconds=5,
        )

        assert result["status_code"] == 200
        assert result["headers"]["x-test"] == "1"
        assert result["text"] == "ok"

        monkeypatch.setattr(httpx, "AsyncClient", original_client)
