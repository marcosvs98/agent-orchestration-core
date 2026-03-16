from __future__ import annotations

from typing import Protocol

from domain.llm.schemas.moderation import ModerationResult


class ModerationProviderPort(Protocol):
    async def moderate(
        self, text: str, config: dict[str, object] | None = None
    ) -> ModerationResult: ...
