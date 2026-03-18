from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


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


class LlmNodeConfigWrapperSchema(BaseModel):
    """Node config that contains an llm block (IntentDetection, ToolSelection, etc.)."""

    llm: LlmNodeConfigSchema | Dict[str, Any] | None = None


class ClarificationNodeConfigSchema(BaseModel):
    """ClarificationNode can have resume_to_node_id and llm."""

    resume_to_node_id: str | None = None
    llm: LlmNodeConfigSchema | Dict[str, Any] | None = None


class ModerationProviderSchema(BaseModel):
    """Primary/fallback moderation provider."""

    provider: str | None = None
    model_alias: str | None = None
    timeout_ms: int | None = None


class ModerationNodeConfigSchema(BaseModel):
    """Config for InputModerationNode."""

    primary: ModerationProviderSchema | Dict[str, Any] | None = None
    fallback: ModerationProviderSchema | Dict[str, Any] | None = None
    fallback_enabled: bool | None = None
    prompt_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class UserContextLayersSchema(BaseModel):
    """Layers for UserContextEnrichmentNode."""

    allow_tenant_knowledge: bool | None = None
    allow_user_memory_structured: bool | None = None
    allow_user_memory_vector: bool | None = None


class UserContextEnrichmentNodeConfigSchema(BaseModel):
    """Config for UserContextEnrichmentNode."""

    publish: bool | None = None
    layers: UserContextLayersSchema | Dict[str, Any] | None = None


def validate_node_config(node_type: str, config: Dict[str, Any] | None) -> None:
    """
    Validate node config by type using explicit mapping. No getattr/setattr.
    Raises pydantic.ValidationError if config does not match the schema for the type.
    """
    if config is None:
        return
    type_to_schema = {
        "IntentDetectionNode": LlmNodeConfigWrapperSchema,
        "ToolSelectionNode": LlmNodeConfigWrapperSchema,
        "ParamExtractionNode": LlmNodeConfigWrapperSchema,
        "ResponseComposer": LlmNodeConfigWrapperSchema,
        "FallbackNodeSLA": LlmNodeConfigWrapperSchema,
        "ClarificationNode": ClarificationNodeConfigSchema,
        "InputModerationNode": ModerationNodeConfigSchema,
        "UserContextEnrichmentNode": UserContextEnrichmentNodeConfigSchema,
    }
    schema_class = type_to_schema.get(node_type)
    if schema_class is not None:
        schema_class.model_validate(config)
