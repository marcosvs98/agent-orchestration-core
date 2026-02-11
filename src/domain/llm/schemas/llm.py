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
    text_format: str | None = "json_object"
    temperature: float | None = 0.2
    max_tokens: int | None = None
    max_latency_ms: int | None = None
    max_cost_usd: float | None = None
    retry_limit: int | None = None
    fallback_model_alias: str | None = None
    available_tools: list[AvailableTool] = []
    prompt_cache_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    prompt_version: int | None = None
    prompt_frozen_hash: str | None = None
    prompt_id: str | None = None
    task_type: LLMTaskType | None = None
    user_id: str | None = None

    conversation_key: str | None = None
    stateless: bool | None = None

    model_config = {"frozen": True}

    def __repr__(self):
        return f"{self.__class__.__name__}({self.task_type})"


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
