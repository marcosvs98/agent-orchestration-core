"""Bounding the provider-side conversation (gap register §4).

History lives in the OpenAI Conversations API behind a 24h Redis mapping. Nothing truncated it, and
when the mapping expired a brand-new empty conversation was created and the whole thread was
silently gone. Growth is now tracked, rolled at a threshold with a carry-forward summary, and a
mapping miss reseeds from that summary instead of starting blank.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.conversation.schemas.continuity import (
    ConversationContinuityPolicy,
    ConversationGrowth,
)
from domain.conversation.services.conversation_continuity_service import (
    ConversationContinuityService,
)
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter

CONVERSATION_KEY = "tenant-a:session-b"


class _FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.counts: dict[str, int] = {}
        self.floats: dict[str, float] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, data, ttl: int = 0):
        self.values[key] = data

    async def delete(self, key: str):
        self.values.pop(key, None)
        self.counts.pop(key, None)
        self.floats.pop(key, None)

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def incrbyfloat_with_ttl(self, key: str, amount: float, ttl: int) -> float:
        self.floats[key] = self.floats.get(key, 0.0) + amount
        return self.floats[key]


def _service(repository: MagicMock | None = None, **policy_kwargs) -> ConversationContinuityService:
    return ConversationContinuityService(
        repository=repository or _repository(),
        cache_adapter=_FakeCache(),
        policy=ConversationContinuityPolicy(**policy_kwargs) if policy_kwargs else None,
    )


def _repository(summary: str | None = None) -> MagicMock:
    repository = MagicMock()
    repository.get = AsyncMock(
        return_value=(
            SimpleNamespace(summary_text=summary, provider_conversation_id=None)
            if summary is not None
            else None
        )
    )
    repository.upsert = AsyncMock()
    repository.set_provider_conversation_id = AsyncMock()
    return repository


class TestGrowthTracking:
    @pytest.mark.asyncio
    async def test_turns_below_the_threshold_do_not_roll_over(self):
        service = _service(max_turns=5, max_estimated_tokens=10_000)

        for _ in range(4):
            decision = await service.record_turn(
                conversation_key=CONVERSATION_KEY, text="a short turn"
            )

        assert decision.should_roll_over is False
        assert decision.growth.turns == 4

    @pytest.mark.asyncio
    async def test_crossing_the_turn_threshold_rolls_over(self):
        service = _service(max_turns=3, max_estimated_tokens=10_000)

        decisions = [
            await service.record_turn(conversation_key=CONVERSATION_KEY, text="turn")
            for _ in range(3)
        ]

        assert [d.should_roll_over for d in decisions] == [False, False, True]
        assert decisions[-1].reason_code == "max_turns"

    @pytest.mark.asyncio
    async def test_crossing_the_token_threshold_rolls_over(self):
        service = _service(max_turns=10_000, max_estimated_tokens=10)

        decision = await service.record_turn(conversation_key=CONVERSATION_KEY, text="word " * 200)

        assert decision.should_roll_over is True
        assert decision.reason_code == "max_estimated_tokens"

    @pytest.mark.asyncio
    async def test_growth_tracking_failure_does_not_force_a_rollover(self):
        """An unavailable counter must not trigger a rollover on every turn."""

        cache = _FakeCache()
        cache.incr_with_ttl = AsyncMock(side_effect=ConnectionError("redis down"))
        service = ConversationContinuityService(repository=_repository(), cache_adapter=cache)

        decision = await service.record_turn(conversation_key=CONVERSATION_KEY, text="t")

        assert decision.should_roll_over is False

    @pytest.mark.asyncio
    async def test_committing_a_rollover_resets_the_counters(self):
        service = _service(max_turns=2, max_estimated_tokens=10_000)
        await service.record_turn(conversation_key=CONVERSATION_KEY, text="one")

        await service.commit_rollover(
            tenant_id=uuid4(),
            conversation_key=CONVERSATION_KEY,
            session_id=uuid4(),
            summary_text="summary so far",
            growth=ConversationGrowth(turns=2, estimated_tokens=100),
            provider_conversation_id=None,
        )
        decision = await service.record_turn(conversation_key=CONVERSATION_KEY, text="two")

        assert decision.growth.turns == 1
        assert decision.should_roll_over is False

    @pytest.mark.asyncio
    async def test_summary_is_trimmed_to_the_policy_limit(self):
        repository = _repository()
        service = ConversationContinuityService(
            repository=repository,
            cache_adapter=_FakeCache(),
            policy=ConversationContinuityPolicy(summary_max_chars=20),
        )

        await service.commit_rollover(
            tenant_id=uuid4(),
            conversation_key=CONVERSATION_KEY,
            session_id=None,
            summary_text="x" * 500,
            growth=ConversationGrowth(turns=1, estimated_tokens=1),
            provider_conversation_id=None,
        )

        assert len(repository.upsert.await_args.kwargs["summary_text"]) == 20


class TestProviderConversationReseeding:
    def _provider(self, cache: _FakeCache, continuity) -> OpenAIProviderAdapter:
        openai_client = MagicMock()
        openai_client.conversations = MagicMock()
        openai_client.conversations.create = AsyncMock(return_value=SimpleNamespace(id="conv_new"))
        return OpenAIProviderAdapter(
            cache_adapter=cache,
            openai_client=openai_client,
            continuity_service=continuity,
        )

    @pytest.mark.asyncio
    async def test_cached_mapping_is_reused(self):
        cache = _FakeCache()
        cache.values["openai:conversation:" + CONVERSATION_KEY] = "conv_existing"
        provider = self._provider(cache, _service())

        result = await provider._get_or_create_conversation_id(CONVERSATION_KEY)

        assert result == "conv_existing"
        provider.openai_client.conversations.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_mapping_miss_with_a_summary_reseeds_the_new_conversation(self):
        """This is the silent-history-loss fix: the replacement starts from the carry-forward."""

        cache = _FakeCache()
        continuity = _service(_repository(summary="the story so far"))
        provider = self._provider(cache, continuity)

        result = await provider._get_or_create_conversation_id(CONVERSATION_KEY)

        assert result == "conv_new"
        create_kwargs = provider.openai_client.conversations.create.await_args.kwargs
        assert "the story so far" in create_kwargs["items"][0]["content"]

    @pytest.mark.asyncio
    async def test_mapping_miss_without_a_summary_starts_clean(self):
        cache = _FakeCache()
        provider = self._provider(cache, _service(_repository(summary=None)))

        await provider._get_or_create_conversation_id(CONVERSATION_KEY)

        assert "items" not in provider.openai_client.conversations.create.await_args.kwargs

    @pytest.mark.asyncio
    async def test_unavailable_carry_forward_still_yields_a_usable_conversation(self):
        cache = _FakeCache()
        continuity = MagicMock()
        continuity.carry_forward_text = AsyncMock(side_effect=RuntimeError("db down"))
        provider = self._provider(cache, continuity)

        assert await provider._get_or_create_conversation_id(CONVERSATION_KEY) == "conv_new"


class TestRollover:
    @pytest.mark.asyncio
    async def test_rollover_persists_the_summary_and_repoints_the_mapping(self):
        cache = _FakeCache()
        cache.values["openai:conversation:" + CONVERSATION_KEY] = "conv_old"
        cache.values["openai:previous_response:" + CONVERSATION_KEY] = "resp_old"
        repository = _repository()
        continuity = ConversationContinuityService(repository=repository, cache_adapter=cache)
        openai_client = MagicMock()
        openai_client.conversations = MagicMock()
        openai_client.conversations.create = AsyncMock(
            return_value=SimpleNamespace(id="conv_rolled")
        )
        provider = OpenAIProviderAdapter(
            cache_adapter=cache,
            openai_client=openai_client,
            continuity_service=continuity,
        )
        tenant_id = uuid4()

        new_id = await provider.roll_over_conversation(
            tenant_id=tenant_id,
            conversation_key=CONVERSATION_KEY,
            session_id=uuid4(),
            summary_text="carry this forward",
            growth=ConversationGrowth(turns=40, estimated_tokens=61_000),
        )

        assert new_id == "conv_rolled"
        assert cache.values["openai:conversation:" + CONVERSATION_KEY] == "conv_rolled"
        assert "openai:previous_response:" + CONVERSATION_KEY not in cache.values

        upsert = repository.upsert.await_args.kwargs
        assert upsert["tenant_id"] == tenant_id
        assert upsert["summary_text"] == "carry this forward"
        assert upsert["turns_covered"] == 40
        assert upsert["estimated_tokens_covered"] == 61_000

        create_kwargs = openai_client.conversations.create.await_args.kwargs
        assert "carry this forward" in create_kwargs["items"][0]["content"]
