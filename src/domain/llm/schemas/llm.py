from enum import StrEnum
from typing import Any, Dict
from pydantic import BaseModel, Field
from domain.execution.services.graph_runtime.execution_plan import AvailableTool


class LLMTaskType(StrEnum):
    INTENT_SELECTION = "INTENT_SELECTION"
    PARAM_EXTRACTION = "PARAM_EXTRACTION"
    SLOT_FILLING = "SLOT_FILLING"
    CLARIFICATION = "CLARIFICATION"
    RESPONSE_RENDER = "RESPONSE_RENDER"


class LLMProviderType(StrEnum):
    OPENAI = "OPENAI"


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    model_alias: str
    max_tokens: int | None = None
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    retry_limit: int | None = None
    fallback_model_alias: str | None = None
    available_tools: list[AvailableTool] = []

    prompt_version: int | None = None
    prompt_frozen_hash: str | None = None
    prompt_id: str | None = None
    task_type: LLMTaskType | None = None

    conversation_key: str | None = None
    stateless: bool | None = None

    model_config = {"frozen": True}


class LLMResult(BaseModel):
    output: Dict[str, Any] = Field(default_factory=dict)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None
    latency_ms: int | None = None
    model_alias: str | None = None
    raw_output: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class LLMProviderSelection(BaseModel):
    provider: str
    provider_model: str
    base_url: str | None = None
    credential_secret_ref: str | None = None
