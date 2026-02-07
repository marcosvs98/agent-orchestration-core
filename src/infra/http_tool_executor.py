from __future__ import annotations

import json

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

        with self.tracer.observe(
            as_type="tool",
            name="domain.infra.http_tool_executor.execute_http",
            input={"method": method.upper(), "url": url},
        ):
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=request_headers,
                    json=json_body if json_body else None,
                )

                try:
                    body = response.json()
                except json.JSONDecodeError:
                    body = response.text

                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": body,
                }
