from __future__ import annotations

import asyncio
from typing import Any, Dict

from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult


class FakeLLMProvider(LLMProviderPort):
    """Deterministic provider used for tests and local development."""

    def __init__(
        self,
        *,
        canned_output: Dict[str, Any] | None = None,
        token_usage: Dict[str, int] | None = None,
        latency_ms: int = 5,
        cost_usd: float | None = None,
    ) -> None:
        self.canned_output = canned_output or {}
        self.token_usage = token_usage or {}
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd

    async def infer(self, request: LLMRequest) -> LLMResult:
        await asyncio.sleep(self.latency_ms / 1000)
        return LLMResult(
            output=self.canned_output,
            token_usage=self.token_usage,
            cost_usd=self.cost_usd,
            latency_ms=self.latency_ms,
            model_alias=request.model_alias,
        )
