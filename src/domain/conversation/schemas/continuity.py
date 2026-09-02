from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from domain.llm.ports.conversation_continuity import ConversationGrowth as ConversationGrowth


class ConversationBinding(BaseModel):
    """Which provider conversation a turn should use, and why."""

    model_config = ConfigDict(frozen=True)

    provider_conversation_id: str
    created: bool = False
    seeded_from_summary: bool = False
    seed_text: str | None = None


class RolloverDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    should_roll_over: bool = False
    reason_code: str | None = None
    growth: ConversationGrowth = ConversationGrowth()


class ConversationContinuityPolicy(BaseModel):
    """Thresholds at which the provider conversation is rolled to a fresh one."""

    max_turns: int = 40
    max_estimated_tokens: int = 60_000
    summary_max_chars: int = 4_000

    def decide(self, growth: ConversationGrowth) -> RolloverDecision:
        if self.max_turns > 0 and growth.turns >= self.max_turns:
            return RolloverDecision(should_roll_over=True, reason_code="max_turns", growth=growth)
        if self.max_estimated_tokens > 0 and growth.estimated_tokens >= self.max_estimated_tokens:
            return RolloverDecision(
                should_roll_over=True, reason_code="max_estimated_tokens", growth=growth
            )
        return RolloverDecision(should_roll_over=False, growth=growth)


class ConversationSummaryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    conversation_key: str
    summary_text: str
    turns_covered: int
    estimated_tokens_covered: int
    provider_conversation_id: str | None = None
    rollover_count: int = 0
