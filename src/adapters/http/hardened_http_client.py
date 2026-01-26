from __future__ import annotations

import asyncio
from typing import Any, Mapping, Sequence

import httpx

RETRY_STATUS_CODES: Sequence[int] = (429, 500, 502, 503, 504)


class HardenedHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.5,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    async def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float | None = None,
    ) -> httpx.Response:
        timeout = (
            timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        )
        attempt = 0
        last_exc: Exception | None = None
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                while attempt <= self.max_retries:
                    try:
                        response = await client.post(
                            url, headers=headers, json=json_body
                        )
                        if response.status_code not in RETRY_STATUS_CODES:
                            return response
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                    attempt += 1
                    if attempt > self.max_retries:
                        break
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)
                if last_exc:
                    raise last_exc

                return response  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            raise exc from exc
