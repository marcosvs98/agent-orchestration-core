from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.governance.schemas.memory_policy import MemoryPolicyDefinition
from domain.governance.schemas.rag_policy import RagPolicyDefinition
from domain.governance.schemas.runtime_policy import RuntimePolicyDefinition


class RuntimePolicyCreate(BaseModel):
    scope: str
    flow_id: UUID | None = None
    version: str = "1"
    policy_definition: RuntimePolicyDefinition


class RuntimePolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    scope: str
    flow_id: UUID | None
    version: str
    status: str
    policy_definition: RuntimePolicyDefinition


class RuntimePolicyUpdate(BaseModel):
    status: str | None = None
    policy_definition: RuntimePolicyDefinition | None = None


class AccessPolicyCreate(BaseModel):
    name: str


class AccessPolicyRules(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] | None = None


class AccessPolicyVersionCreate(BaseModel):
    status: str = "DRAFT"
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    rules: AccessPolicyRules = Field(default_factory=AccessPolicyRules)


class AccessPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str


class AccessPolicyVersionResponse(BaseModel):
    id: UUID
    access_policy_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    rules: AccessPolicyRules


class RateLimitPolicyCreate(BaseModel):
    name: str


class RateLimitPolicyVersionCreate(BaseModel):
    status: str = "DRAFT"
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    action: str
    principal_type: str
    limit: int
    window_seconds: int


class RateLimitPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str


class RateLimitPolicyVersionResponse(BaseModel):
    id: UUID
    rate_limit_policy_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    action: str
    principal_type: str
    limit: int
    window_seconds: int


class BillingPolicyCreate(BaseModel):
    name: str


class BillingPolicyRulesSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class BillingPolicyVersionCreate(BaseModel):
    status: str = "DRAFT"
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    rules: BillingPolicyRulesSchema = Field(default_factory=BillingPolicyRulesSchema)


class BillingPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str


class BillingPolicyVersionResponse(BaseModel):
    id: UUID
    billing_policy_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    rules: BillingPolicyRulesSchema


class MemoryPolicyCreate(BaseModel):
    name: str


class MemoryPolicyVersionCreate(BaseModel):
    status: str = "DRAFT"
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    definition: MemoryPolicyDefinition


class MemoryPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str


class MemoryPolicyVersionResponse(BaseModel):
    id: UUID
    memory_policy_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    definition: MemoryPolicyDefinition


class RagPolicyCreate(BaseModel):
    name: str


class RagPolicyVersionCreate(BaseModel):
    status: str = "DRAFT"
    version_major: int = 1
    version_minor: int = 0
    version_patch: int = 0
    definition: RagPolicyDefinition


class RagPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str


class RagPolicyVersionResponse(BaseModel):
    id: UUID
    rag_policy_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    definition: RagPolicyDefinition
