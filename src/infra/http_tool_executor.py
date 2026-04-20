from __future__ import annotations

import json
from urllib.parse import urlencode

import httpx

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.tools.ports.tool_executor import ToolExecutorPort


class HttpToolExecutor(ToolExecutorPort):
    """HTTP tool executor for making external API calls."""

    def __init__(self, tracer: RuntimeTracerPort) -> None:
        self.tracer = tracer

    async def execute_http(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict,
        timeout_seconds: float,
    ) -> dict:
        request_headers = {"Accept-Encoding": "identity", **headers}

        m = method.upper()
        req_json = None
        req_params = None
        if m == "GET":
            if json_body:
                req_params = {k: v for k, v in json_body.items() if v is not None}
                if not req_params:
                    req_params = None
            else:
                req_params = None
        else:
            if json_body:
                req_json = {k: v for k, v in json_body.items() if v is not None}
                if not req_json:
                    req_json = None
            else:
                req_json = None

        if req_params:
            payload_bytes = urlencode([(str(k), str(v)) for k, v in req_params.items()]).encode(
                "utf-8"
            )
        elif req_json:
            payload_bytes = json.dumps(json_body, default=str).encode("utf-8")
        else:
            payload_bytes = b""
        trace_input = {
            "method": m,
            "url": url,
            "timeout_seconds": timeout_seconds,
            "header_keys": sorted(request_headers.keys()),
            "request_size": len(payload_bytes),
        }

        with self.tracer.observe(
            as_type="tool",
            name="domain.infra.http_tool_executor.execute_http",
            input=trace_input,
        ) as tool_handle:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.request(
                    method=m,
                    url=url,
                    headers=request_headers,
                    json=req_json,
                    params=req_params,
                )

                try:
                    body = response.json()
                except ValueError:
                    body = response.text

                result = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": body,
                }

                if tool_handle:
                    tool_handle.success(
                        output={
                            "status_code": response.status_code,
                            "response_size": len(response.content),
                        }
                    )

                return result
