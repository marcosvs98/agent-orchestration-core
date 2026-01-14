from enum import StrEnum
from typing import Any, Dict

from pydantic import BaseModel, Field


class LLMTaskType(StrEnum):
    INTENT_SELECTION = "INTENT_SELECTION"
    PARAM_EXTRACTION = "PARAM_EXTRACTION"
    CLARIFICATION = "CLARIFICATION"
    RESPONSE_RENDER = "RESPONSE_RENDER"


class LLMRequest(BaseModel):
    task_type: LLMTaskType
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    model_alias: str
    max_tokens: int | None = None
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    retry_limit: int | None = None
    fallback_model_alias: str | None = None

    model_config = {"frozen": True}


class LLMResult(BaseModel):
    output: Dict[str, Any] = Field(default_factory=dict)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None
    latency_ms: int | None = None
    model_alias: str | None = None

    model_config = {"frozen": True}


class LLMProviderSelection(BaseModel):
    provider: str
    provider_model: str
    base_url: str | None = None
    credential_secret_ref: str | None = None