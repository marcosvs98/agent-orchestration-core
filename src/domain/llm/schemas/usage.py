from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class LLMUsageRecord(BaseModel):
    """One provider interaction, as it happened.

    Emitted by LLM nodes and persisted by the step runner. `inference_layer` distinguishes a real
    provider call from a semantic-cache hit, so cached turns are not mistaken for spend.
    """

    model_config = ConfigDict(frozen=True)

    provider: str | None = None
    provider_model: str | None = None
    task_type: str | None = None
    inference_layer: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal | None = None
    agent_version_id: UUID | None = None
    ai_execution_policy_version_id: UUID | None = None
    latency_ms: int | None = None

    @field_validator("latency_ms", mode="before")
    @classmethod
    def _whole_milliseconds(cls, value: int | float | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("latency_ms must be numeric")
        if isinstance(value, (int, float)):
            return round(value)
        raise ValueError("latency_ms must be numeric")
