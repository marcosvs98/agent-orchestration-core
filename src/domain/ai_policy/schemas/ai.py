from uuid import UUID

from pydantic import BaseModel


class AITaskContextFlags(BaseModel):
    allow_rag_tenant: bool = False
    allow_user_memory_structured: bool = False
    allow_user_memory_vector: bool = False
    rag_config_id: UUID | None = None
    allow_session_context: bool = False
    allow_memory_write: bool = False


class Model(BaseModel):
    id: UUID
    name: str


class ModelCreate(BaseModel):
    name: str


class NodeAIExecutionPolicyBinding(BaseModel):
    id: UUID
    node_id: UUID
    ai_execution_policy_version_id: UUID


class NodeAIExecutionPolicyBindingCreate(BaseModel):
    node_id: UUID
    ai_execution_policy_version_id: UUID


class AIExecutionPolicy(BaseModel):
    id: UUID
    description: str | None = None


class AIExecutionPolicyCreate(BaseModel):
    description: str | None = None


class AIExecutionPolicyVersion(BaseModel):
    id: UUID
    ai_execution_policy_id: UUID
    model_id: UUID
    notes: str | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None


class AIExecutionPolicyVersionCreate(BaseModel):
    ai_execution_policy_id: UUID
    model_id: UUID
    notes: str | None = None
    source_version_id: UUID | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None
