from __future__ import annotations

from typing import Protocol

from domain.llm.schemas.llm import LLMRequest, LLMResult


class LLMProviderPort(Protocol):
    async def infer(
        self, request: LLMRequest
    ) -> LLMResult:  # pragma: no cover - interface
        ...
