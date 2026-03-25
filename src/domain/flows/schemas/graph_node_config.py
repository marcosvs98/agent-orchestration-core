from __future__ import annotations

from typing import Any, Dict, List, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LlmNodeConfigSchema(BaseModel):
    """Config for LLM-backed nodes (intent, tool selection, param extraction, etc.)."""

    task_type: str | None = None
    provider: str | None = None
    model_alias: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    use_system_prompt: bool | None = None
    use_system_context: bool | None = None
    max_tokens: int | None = None
    completion_budget: Dict[str, float] | None = None
    use_conversation_history: bool | None = None


class RagPipelineExtensionSchema(BaseModel):
    retriever_profile_id: UUID | None = None
    ingestor_profile_id: UUID | None = None
    retriever_when: Literal["always", "on_flag", "never"] | None = None
    ingestor_trigger: str | None = Field(default=None, max_length=256)


class LlmNodeConfigWrapperSchema(BaseModel):
    """Node config that contains an llm block (IntentClassifier, ToolResolver, etc.)."""

    llm: LlmNodeConfigSchema | Dict[str, Any] | None = None
    rag_pipeline: RagPipelineExtensionSchema | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1, le=64)


class QueryClarifierNodeConfigSchema(BaseModel):
    """QueryClarifier can have resume_to_node_id and llm."""

    resume_to_node_id: str | None = None
    llm: LlmNodeConfigSchema | Dict[str, Any] | None = None


class ModerationProviderSchema(BaseModel):
    """Primary/fallback moderation provider."""

    provider: str | None = None
    model_alias: str | None = None
    timeout_ms: int | None = None


class ModerationNodeConfigSchema(BaseModel):
    """Config for ContentModeration."""

    primary: ModerationProviderSchema | Dict[str, Any] | None = None
    fallback: ModerationProviderSchema | Dict[str, Any] | None = None
    fallback_enabled: bool | None = None
    prompt_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class MemoryCommitDataMergeRuleSchema(BaseModel):
    """Maps a prior node output field into the memory commit payload."""

    from_node_id: str
    path: str = ""
    target_key: str


class MemoryCommitNodeConfigSchema(BaseModel):
    schema_id: str
    schema_version: int = 1
    source: str = "explicit_user"
    rag_config_id: str
    data: Dict[str, Any] | None = None
    data_merge: List[MemoryCommitDataMergeRuleSchema] | None = None
    literal_overlay: Dict[str, Any] | None = None


class ContextSummarizerNodeConfigSchema(BaseModel):
    source_node_id: str
    min_payload_bytes_to_run: int = Field(default=1, ge=0)
    llm: LlmNodeConfigSchema | Dict[str, Any] | None = None


def validate_node_config(node_type: str, config: Dict[str, Any] | None) -> None:
    """
    Validate node config by type using explicit mapping. No getattr/setattr.
    Raises pydantic.ValidationError if config does not match the schema for the type.
    """
    if config is None:
        return
    type_to_schema = {
        "IntentClassifier": LlmNodeConfigWrapperSchema,
        "ToolResolver": LlmNodeConfigWrapperSchema,
        "ToolInputFiller": LlmNodeConfigWrapperSchema,
        "ResponseBuilder": LlmNodeConfigWrapperSchema,
        "HumanFallback": LlmNodeConfigWrapperSchema,
        "QueryClarifier": QueryClarifierNodeConfigSchema,
        "ContentModeration": ModerationNodeConfigSchema,
        "MemoryCommitNode": MemoryCommitNodeConfigSchema,
        "ContextSummarizer": ContextSummarizerNodeConfigSchema,
    }
    schema_class = type_to_schema.get(node_type)
    if schema_class is not None:
        schema_class.model_validate(config)
