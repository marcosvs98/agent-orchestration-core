import json

import httpx

from domain.tools.ports.tool_executor import ToolExecutorPort


class HttpToolExecutor(ToolExecutorPort):
    """HTTP tool executor for making external API calls."""

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
