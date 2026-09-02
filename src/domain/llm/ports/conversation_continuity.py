from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConversationGrowth(BaseModel):
    """Estimated size of a provider-side conversation, as tracked on our side.

    The provider owns the transcript, so this is an estimate maintained from the text we send and
    receive — it is what rollover thresholds act on.
    """

    model_config = ConfigDict(frozen=True)

    turns: int = 0
    estimated_tokens: int = 0


class ConversationContinuityPort(Protocol):
    """What the provider adapter needs in order to survive losing a conversation.

    Declared here, in the LLM domain, so the adapter never imports the conversation domain — the
    implementation lives in `domain/conversation` and satisfies this structurally.
    """

    async def carry_forward_text(self, *, conversation_key: str) -> str | None: ...

    async def commit_rollover(
        self,
        *,
        tenant_id: UUID,
        conversation_key: str,
        session_id: UUID | None,
        summary_text: str,
        growth: ConversationGrowth,
        provider_conversation_id: str | None,
    ) -> None: ...

    async def bind_provider_conversation(
        self, *, conversation_key: str, provider_conversation_id: str
    ) -> None: ...
