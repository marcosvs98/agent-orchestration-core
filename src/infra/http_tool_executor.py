import httpx

from domain.tools.ports.tool_executor import ToolExecutorPort


class HttpToolExecutor(ToolExecutorPort):
    async def execute_http(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict,
        timeout_seconds: float,
    ) -> dict:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
            )
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "text": response.text,
            }
