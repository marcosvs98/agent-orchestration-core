from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SemanticCacheEntry(BaseModel):
    cache_id: UUID
    task_type: str
    response: dict[str, Any]
    similarity_score: float
    model_alias: str | None = None
    inference_layer: str
    created_at: datetime


class CacheLookupResult(BaseModel):
    hit: bool
    entry: SemanticCacheEntry | None = None
    query_embedding: list[float] | None = None


class InferenceLayerPolicy(BaseModel):
    cache_enabled: bool = True
    cache_similarity_threshold: float = 0.92
    cache_ttl_seconds: int = 3600
    slm_enabled: bool = True
    slm_eligible_tasks: list[str] = Field(
        default_factory=lambda: [
            "intent_selection",
            "tool_selection",
        ]
    )
    slm_provider: str = "SLM_LOCAL"
    slm_model_alias: str = "smollm2-360m"
    escalation_on_schema_mismatch: bool = True
