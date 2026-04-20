from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RuntimePolicyScope(StrEnum):
    TENANT = "TENANT"
    FLOW = "FLOW"


class RuntimePolicySource(StrEnum):
    FLOW = "FLOW"
    TENANT = "TENANT"
    DEFAULT = "DEFAULT"


class RuntimePolicyLimitsSchema(BaseModel):
    max_nodes: int | None = None
    max_depth: int | None = None
    max_edges_per_node: int | None = None
    max_total_duration_ms: int | None = None
    max_node_duration_ms: int | None = None
    max_loop_iterations: int | None = None
    tool_fanout_max_concurrency: int | None = None


class RuntimePolicyLlmInferenceLayersSchema(BaseModel):
    cache_enabled: bool | None = None
    cache_similarity_threshold: float | None = None
    cache_ttl_seconds: int | None = None
    slm_enabled: bool | None = None
    slm_eligible_tasks: list[str] | None = None
    slm_provider: str | None = None
    slm_model_alias: str | None = None
    escalation_on_schema_mismatch: bool | None = None


class RuntimePolicyLlmSchema(BaseModel):
    max_retries: int | None = None
    timeout_ms: int | None = None
    stream_enabled: bool | None = None
    stream_eligible_tasks: list[str] | None = None
    history_enabled_tasks: list[str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    inference_layers: RuntimePolicyLlmInferenceLayersSchema | Dict[str, Any] | None = None


class RuntimePolicyExecutionSchema(BaseModel):
    fail_on_multiple_true_edges: bool | None = None
    fail_on_missing_graph: bool | None = None
    allow_parallel_nodes: bool | None = None
    strict_contract_mode: bool | None = None


class RuntimePolicyToolsCircuitBreakerSchema(BaseModel):
    failure_threshold: int | None = None
    window_seconds: int | None = None


class RuntimePolicyToolsSchema(BaseModel):
    max_retries: int | None = None
    circuit_breaker: RuntimePolicyToolsCircuitBreakerSchema | Dict[str, Any] | None = None


class RuntimePolicyModerationProviderSchema(BaseModel):
    provider: str | None = None
    model_alias: str | None = None
    timeout_ms: int | None = None


class RuntimePolicyModerationSchema(BaseModel):
    primary: RuntimePolicyModerationProviderSchema | Dict[str, Any] | None = None
    fallback: RuntimePolicyModerationProviderSchema | Dict[str, Any] | None = None
    fallback_enabled: bool | None = None
    prompt_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class RuntimePolicyFallbackSlaSchema(BaseModel):
    primary: RuntimePolicyModerationProviderSchema | Dict[str, Any] | None = None
    fallback_enabled: bool | None = None
    prompt_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class RuntimePolicyUserContextEnrichmentLayersSchema(BaseModel):
    allow_tenant_knowledge: bool | None = None
    allow_user_memory_structured: bool | None = None
    allow_user_memory_vector: bool | None = None


class RuntimePolicyUserContextEnrichmentSchema(BaseModel):
    enabled: bool | None = None
    gating: bool | None = None
    default_layers_when_published: (
        RuntimePolicyUserContextEnrichmentLayersSchema | Dict[str, Any] | None
    ) = None


class RuntimePolicyMemoryExtractionLlmSchema(BaseModel):
    provider: str | None = None
    model_alias: str | None = None
    prompt: str | None = None
    task_type: str | None = None


class RuntimePolicyMemoryExtractionSchema(BaseModel):
    enabled: bool | None = None
    rag_config_id: str | None = None
    preference_schema_id: str | None = None
    profile_schema_id: str | None = None
    llm: RuntimePolicyMemoryExtractionLlmSchema | Dict[str, Any] | None = None


class RuntimePolicyMemoryRetrievalTemporalScoringSchema(BaseModel):
    enabled: bool | None = None
    half_life_seconds: int | None = None
    timestamp_source: str | None = None
    candidate_multiplier: int | None = None


class RuntimePolicyMemoryRetrievalSchema(BaseModel):
    temporal_scoring: RuntimePolicyMemoryRetrievalTemporalScoringSchema | Dict[str, Any] | None = (
        None
    )


class RuntimePolicyDefinition(BaseModel):
    limits: RuntimePolicyLimitsSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyLimitsSchema
    )
    execution: RuntimePolicyExecutionSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyExecutionSchema
    )
    tools: RuntimePolicyToolsSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyToolsSchema
    )
    llm: RuntimePolicyLlmSchema | Dict[str, Any] = Field(default_factory=RuntimePolicyLlmSchema)
    moderation: RuntimePolicyModerationSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyModerationSchema
    )
    fallback_sla: RuntimePolicyFallbackSlaSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyFallbackSlaSchema
    )
    memory_extraction: RuntimePolicyMemoryExtractionSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyMemoryExtractionSchema
    )
    memory_retrieval: RuntimePolicyMemoryRetrievalSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyMemoryRetrievalSchema
    )
    user_context_enrichment: RuntimePolicyUserContextEnrichmentSchema | Dict[str, Any] = Field(
        default_factory=RuntimePolicyUserContextEnrichmentSchema
    )


class ResolvedRuntimePolicy(BaseModel):
    source: RuntimePolicySource
    runtime_policy_id: Optional[UUID] = None
    version: str
    definition: RuntimePolicyDefinition
    scope: RuntimePolicyScope
    flow_id: Optional[UUID] = None
