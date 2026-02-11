from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryExtractionLLMConfig(BaseModel):
    provider: str = "OPENAI"
    model_alias: str = "gpt-4o-mini"
    prompt: str
    task_type: str = "RESPONSE_RENDER"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int | None = None
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    retry_limit: int | None = None
    fallback_model_alias: str | None = None


class MemoryExtractionConfig(BaseModel):
    enabled: bool = False
    rag_config_id: UUID
    preference_schema_id: str
    profile_schema_id: str
    llm: MemoryExtractionLLMConfig


class ExtractedPreferenceItem(BaseModel):
    preference_key: str | None = None
    preference_value: object


class ExtractedVectorMemoryItem(BaseModel):
    schema_id: str
    schema_version: int
    data: dict[str, object] = Field(default_factory=dict)


class MemoryExtractionLLMOutput(BaseModel):
    preferences: list[ExtractedPreferenceItem] = Field(default_factory=list)
    profile_patch: dict[str, object] | None = None
    vector_memory: list[ExtractedVectorMemoryItem] = Field(default_factory=list)


class MemoryExtractionSummary(BaseModel):
    attempted_preferences: int = 0
    attempted_profile: int = 0
    attempted_vector: int = 0
    applied_preferences: int = 0
    applied_profile: int = 0
    applied_vector: int = 0
    ignored_preferences: int = 0
    ignored_profile: int = 0
    ignored_vector: int = 0
