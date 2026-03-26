from abc import ABC, abstractmethod
from uuid import UUID
from domain.ai_policy.schemas.ai import (
    AIExecutionPolicy,
    AIExecutionPolicyCreate,
    AIExecutionPolicyVersion,
    AIExecutionPolicyVersionCreate,
    Model,
    ModelCreate,
    NodeAIExecutionPolicyBinding,
    NodeAIExecutionPolicyBindingCreate,
)
from exceptions.service_exceptions import NotImplementedServiceException
from domain.common.schemas.change import ChangeRequest


class AIServicePort(ABC):
    @abstractmethod
    async def create_ai_execution_policy(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_create: AIExecutionPolicyCreate,
        principal_id: str,
    ) -> AIExecutionPolicy:
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_version_create: AIExecutionPolicyVersionCreate,
        principal_id: str,
    ) -> AIExecutionPolicyVersion:
        raise NotImplementedServiceException()

    @abstractmethod
    async def validate_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
    ) -> AIExecutionPolicyVersion:
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_models(self) -> list[Model]:
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_model(self, *, model_create: ModelCreate) -> Model:
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_ai_execution_policy_versions(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str | None = None,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[AIExecutionPolicyVersion]:
        raise NotImplementedServiceException()

    @abstractmethod
    async def publish_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        raise NotImplementedServiceException()

    @abstractmethod
    async def deprecate_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        raise NotImplementedServiceException()

    @abstractmethod
    async def disable_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_node_ai_execution_policy_binding(
        self,
        *,
        node_ai_execution_policy_binding_create: NodeAIExecutionPolicyBindingCreate,
    ) -> NodeAIExecutionPolicyBinding:
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_node_ai_execution_policy_bindings(
        self,
        *,
        node_id: UUID | None = None,
        ai_execution_policy_version_id: UUID | None = None,
        limit: int = 200,
    ) -> list[NodeAIExecutionPolicyBinding]:
        raise NotImplementedServiceException()

    @abstractmethod
    async def delete_node_ai_execution_policy_binding(
        self, *, binding_id: UUID
    ) -> None:
        raise NotImplementedServiceException()
