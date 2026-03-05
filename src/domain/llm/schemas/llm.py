from enum import StrEnum
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field
from domain.execution.services.graph_runtime.execution_plan import AvailableTool


class LLMTaskType(StrEnum):
    INTENT_SELECTION = "intent_selection"
    TOOL_SELECTION = "tool_selection"
    PARAM_EXTRACTION = "param_extraction"
    SLOT_FILLING = "slot_filling"
    CLARIFICATION = "clarification"
    RESPONSE_RENDER = "response_render"
    MEMORY_EXTRACTION = "memory_extraction"  # Todo: needs-clarification: removing this enum member requires changing MemoryExtractionProcessor task typing and event contracts.


class LLMProviderType(StrEnum):
    OPENAI = "OPENAI"
    SLM_LOCAL = "SLM_LOCAL"


class InferenceLayer(StrEnum):
    CACHE = "CACHE"
    SLM = "SLM"
    LLM = "LLM"


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "developer", "tool"]
    content: str

    model_config = {"frozen": True}


class LLMRequest(BaseModel):
    prompt: str = ""
    system_prompt: str | None = None
    system_context: str | None = None
    user_message: str | None = None
    user_payload: Dict[str, Any] = Field(default_factory=dict)
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    messages: list[LLMMessage] = Field(default_factory=list)
    input_schema: Dict[str, Any] | None = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    json_schema: Dict[str, Any] | None = None
    json_schema_name: str | None = None
    model_alias: str
    text_format: str | None = "json_object"
    temperature: float | None = 0.2
    max_tokens: int | None = None
    max_latency_ms: int | None = 5000  # Todo: Create env of this
    max_cost_usd: float | None = None
    retry_limit: int | None = None
    fallback_model_alias: str | None = None
    available_tools: list[AvailableTool] = Field(default_factory=list)
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
    inference_layer: InferenceLayer | None = None

    model_config = {"frozen": True}


class LLMProviderSelection(BaseModel):
    provider: str
    provider_model: str
    base_url: str | None = None
    credential_secret_ref: str | None = None
