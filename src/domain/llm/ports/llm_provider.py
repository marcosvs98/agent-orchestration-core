from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from domain.llm.schemas.llm import LLMRequest, LLMResult


class LLMProviderPort(Protocol):
    async def infer(
        self,
        request: LLMRequest,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResult:  # pragma: no cover - interface
        ...
