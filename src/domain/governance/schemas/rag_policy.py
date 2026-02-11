from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from domain.llm.schemas.llm import LLMTaskType


class RagPolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class RagActivationScope(StrEnum):
    TENANT_KNOWLEDGE = "TENANT_KNOWLEDGE"
    USER_MEMORY_VECTOR = "USER_MEMORY_VECTOR"


class RagScopePolicy(BaseModel):
    enabled: bool = False
    allowed_tool_config_ids: list[UUID] = Field(default_factory=list)


class RagTaskDefaults(BaseModel):
    tenant_knowledge: RagScopePolicy = Field(default_factory=RagScopePolicy)
    user_memory_vector: RagScopePolicy = Field(default_factory=RagScopePolicy)


class RagPolicyDefinition(BaseModel):
    defaults: dict[LLMTaskType, RagTaskDefaults] = Field(default_factory=dict)
    require_published_rag_config: bool = True
    top_k_cap: int | None = None
    min_query_chars_by_scope: dict[RagActivationScope, int] = Field(
        default_factory=lambda: {
            RagActivationScope.TENANT_KNOWLEDGE: 8,
            RagActivationScope.USER_MEMORY_VECTOR: 8,
        }
    )
    allow_structured_input: bool = False


class ResolvedRagPolicySource(StrEnum):
    TENANT_ACTIVE = "TENANT_ACTIVE"
    DEFAULT_NONE = "DEFAULT_NONE"


class ResolvedRagPolicy(BaseModel):
    source: ResolvedRagPolicySource
    tenant_id: UUID
    policy_version_id: UUID | None = None
    definition: RagPolicyDefinition | None = None


class RagActivationDecisionReason(StrEnum):
    STRUCTURAL_DENY = "STRUCTURAL_DENY"
    POLICY_MISSING = "POLICY_MISSING"
    POLICY_DENY = "POLICY_DENY"
    RAG_CONFIG_MISSING = "RAG_CONFIG_MISSING"
    RAG_CONFIG_NOT_FOUND = "RAG_CONFIG_NOT_FOUND"
    RAG_CONFIG_TENANT_MISMATCH = "RAG_CONFIG_TENANT_MISMATCH"
    RAG_CONFIG_NOT_PUBLISHED = "RAG_CONFIG_NOT_PUBLISHED"
    USER_ID_MISSING = "USER_ID_MISSING"
    INPUT_EMPTY = "INPUT_EMPTY"
    INPUT_TOO_SHORT = "INPUT_TOO_SHORT"
    INPUT_STRUCTURED = "INPUT_STRUCTURED"
    TOOL_CONFIG_EXPLICIT_DENY = "TOOL_CONFIG_EXPLICIT_DENY"
    TOOL_CONFIG_EXPLICIT_ALLOW = "TOOL_CONFIG_EXPLICIT_ALLOW"
    POLICY_DEFAULT_ALLOW = "POLICY_DEFAULT_ALLOW"


class RagActivationDecision(BaseModel):
    enabled: bool
    scope: RagActivationScope
    reason: RagActivationDecisionReason
    policy_version_id: UUID | None = None
    effective_top_k: int | None = None
    effective_filters_override: dict[str, object] | None = None
