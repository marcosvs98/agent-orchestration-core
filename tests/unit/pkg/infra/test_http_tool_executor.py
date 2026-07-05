import httpx
import pytest

from infra.http_tool_executor import HttpToolExecutor


class _FakeHandle:
    def __init__(self) -> None:
        self.output = None
        self.error_payload = None

    def success(self, *, output, metadata=None, **kwargs) -> None:
        self.output = output

    def error(self, *, error_type, error_message, output=None, metadata=None, **kwargs) -> None:
        self.error_payload = {
            "error_type": error_type,
            "error_message": error_message,
            "output": output,
        }


class _FakeTracer:
    def __init__(self) -> None:
        self.inputs = []
        self.handle = _FakeHandle()

    def observe(self, *, as_type, name, input, metadata=None):
        self.inputs.append(input)

        class _Ctx:
            def __enter__(_self):
                return self.handle

            def __exit__(_self, exc_type, exc, tb):
                return False

        return _Ctx()


class TestHttpToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_http_returns_status_headers_body_and_sanitized_trace(
        self, monkeypatch
    ):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"x-test": "1"}, text="ok")

        transport = httpx.MockTransport(handler)

        original_client = httpx.AsyncClient

        class PatchedAsyncClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, transport=transport, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)

        tracer = _FakeTracer()
        executor = HttpToolExecutor(tracer=tracer)
        result = await executor.execute_http(
            method="POST",
            url="https://example.com",
            headers={"Authorization": "secret"},
            json_body={"a": 1},
            timeout_seconds=5,
        )

        assert result["status_code"] == 200
        assert result["headers"]["x-test"] == "1"
        assert result["body"] == "ok"
        assert tracer.inputs
        assert "headers" not in tracer.inputs[0]
        assert "json_body" not in tracer.inputs[0]
        assert tracer.inputs[0]["url_host"] == "example.com"
        assert tracer.inputs[0]["url_path"] is None
        assert "header_keys" in tracer.inputs[0]
        assert "request_size" in tracer.inputs[0]
        assert tracer.handle.output == {"status_code": 200, "response_size": 2}

        monkeypatch.setattr(httpx, "AsyncClient", original_client)

    @pytest.mark.asyncio
    async def test_execute_http_records_transport_failure(self, monkeypatch):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        transport = httpx.MockTransport(handler)
        original_client = httpx.AsyncClient

        class PatchedAsyncClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, transport=transport, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)

        tracer = _FakeTracer()
        executor = HttpToolExecutor(tracer=tracer)

        with pytest.raises(httpx.ConnectError):
            await executor.execute_http(
                method="GET",
                url="https://example.com/api/v1/items?token=secret",
                headers={},
                json_body={},
                timeout_seconds=5,
            )

        assert tracer.handle.error_payload is not None
        assert tracer.handle.error_payload["error_type"] == "ConnectError"
        assert tracer.inputs[0]["url_host"] == "example.com"
        assert tracer.inputs[0]["url_path"] == "/api/v1/items"

        monkeypatch.setattr(httpx, "AsyncClient", original_client)
