from __future__ import annotations

from uuid import UUID

import tiktoken

from adapters.cache.redis_adapter import RedisAdapter
from adapters.observability.logging import get_logger
from domain.conversation.repositories.conversation_summary_repository import (
    ConversationSummaryRepository,
)
from domain.conversation.schemas.continuity import (
    ConversationContinuityPolicy,
    ConversationGrowth,
    RolloverDecision,
)

logger = get_logger(__name__)

_ENCODING_NAME = "cl100k_base"
_GROWTH_TTL_SECONDS = 60 * 60 * 24 * 30


class ConversationContinuityService:
    """Bounds a provider-side conversation and preserves it across rollovers.

    The transcript lives with the provider, so its size is not directly observable here. Growth is
    therefore *estimated* on our side from the text we send and receive, and the estimate is what
    the thresholds act on. That is the accepted trade-off of keeping provider-side caching; the
    alternative is owning history locally and re-sending it on every call.
    """

    def __init__(
        self,
        *,
        repository: ConversationSummaryRepository,
        cache_adapter: RedisAdapter,
        policy: ConversationContinuityPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.cache_adapter = cache_adapter
        self.policy = policy or ConversationContinuityPolicy()

    @staticmethod
    def _turns_key(conversation_key: str) -> str:
        return f"conversation:growth:turns:{conversation_key}"

    @staticmethod
    def _tokens_key(conversation_key: str) -> str:
        return f"conversation:growth:tokens:{conversation_key}"

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        try:
            return len(tiktoken.get_encoding(_ENCODING_NAME).encode(text))
        except Exception:
            return max(1, len(text) // 4)

    async def carry_forward_text(self, *, conversation_key: str) -> str | None:
        """Summary to seed a conversation with, when one exists."""

        record = await self.repository.get(conversation_key=conversation_key)
        return record.summary_text if record else None

    async def record_turn(
        self,
        *,
        conversation_key: str,
        policy: ConversationContinuityPolicy | None = None,
        text: str,
    ) -> RolloverDecision:
        effective = policy or self.policy
        try:
            turns = await self.cache_adapter.incr_with_ttl(
                self._turns_key(conversation_key), ttl=_GROWTH_TTL_SECONDS
            )
            tokens = await self.cache_adapter.incrbyfloat_with_ttl(
                self._tokens_key(conversation_key),
                float(self.estimate_tokens(text)),
                ttl=_GROWTH_TTL_SECONDS,
            )
        except Exception:
            logger.exception("conversation_growth_not_tracked", conversation_key=conversation_key)
            return RolloverDecision(should_roll_over=False)

        growth = ConversationGrowth(
            turns=int(turns) if isinstance(turns, int) else 0,
            estimated_tokens=int(tokens),
        )
        return effective.decide(growth)

    async def commit_rollover(
        self,
        *,
        tenant_id: UUID,
        conversation_key: str,
        session_id: UUID | None,
        summary_text: str,
        growth: ConversationGrowth,
        provider_conversation_id: str | None,
        policy: ConversationContinuityPolicy | None = None,
    ) -> None:
        """Persist the carry-forward and reset the growth counters for the new conversation."""

        effective = policy or self.policy
        trimmed = summary_text[: effective.summary_max_chars]
        await self.repository.upsert(
            tenant_id=tenant_id,
            conversation_key=conversation_key,
            session_id=session_id,
            summary_text=trimmed,
            turns_covered=growth.turns,
            estimated_tokens_covered=growth.estimated_tokens,
            provider_conversation_id=provider_conversation_id,
        )
        await self._reset_growth(conversation_key)

    async def _reset_growth(self, conversation_key: str) -> None:
        try:
            await self.cache_adapter.delete(self._turns_key(conversation_key))
            await self.cache_adapter.delete(self._tokens_key(conversation_key))
        except Exception:
            logger.exception("conversation_growth_not_reset", conversation_key=conversation_key)

    async def bind_provider_conversation(
        self, *, conversation_key: str, provider_conversation_id: str
    ) -> None:
        await self.repository.set_provider_conversation_id(
            conversation_key=conversation_key,
            provider_conversation_id=provider_conversation_id,
        )
