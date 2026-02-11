from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryPolicySource(StrEnum):
    EXPLICIT_USER = "explicit_user"
    INFERRED_LLM = "inferred_llm"
    TOOL_OUTPUT = "tool_output"
    ADMIN_SEED = "admin_seed"


class MemoryPolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class MemoryWriteTarget(StrEnum):
    USER_PREFERENCE = "USER_PREFERENCE"
    USER_MEMORY_PROFILE = "USER_MEMORY_PROFILE"
    USER_MEMORY_VECTOR = "USER_MEMORY_VECTOR"


class PreferenceOverwriteMode(StrEnum):
    SOURCE_PRIORITY = "SOURCE_PRIORITY"


class PreferenceUpdatePolicy(BaseModel):
    fixed_key: str | None = None
    allowed_keys: list[str] = Field(default_factory=list)
    ignore_if_unchanged: bool = True
    overwrite_mode: PreferenceOverwriteMode = PreferenceOverwriteMode.SOURCE_PRIORITY


class ConsentDefinition(BaseModel):
    required: bool = False
    preference_key: str = "memory.consent"
    required_for_sources: list[MemoryPolicySource] = Field(default_factory=list)


class AllowedSchema(BaseModel):
    schema_id: str
    max_item_bytes: int | None = None
    allow_fields: dict[str, object] | None = None
    write_targets: list[MemoryWriteTarget] = Field(default_factory=list)
    preference_update: PreferenceUpdatePolicy | None = None


class MemoryPolicyDefinition(BaseModel):
    retention_ttl_seconds: int = 2_592_000
    consent: ConsentDefinition = Field(default_factory=ConsentDefinition)
    allowed_sources: list[MemoryPolicySource] = Field(default_factory=list)
    allowed_schemas: list[AllowedSchema] = Field(default_factory=list)


class ResolvedMemoryPolicySource(StrEnum):
    TENANT_ACTIVE = "TENANT_ACTIVE"
    DEFAULT_NONE = "DEFAULT_NONE"


class ResolvedMemoryPolicy(BaseModel):
    source: ResolvedMemoryPolicySource
    tenant_id: UUID
    policy_version_id: UUID | None = None
    definition: MemoryPolicyDefinition | None = None


class UserMemoryItem(BaseModel):
    schema_id: str
    schema_version: int
    data: dict[str, object] = Field(default_factory=dict)
    source: MemoryPolicySource
    observed_at: datetime | None = None
    rag_config_id: UUID
