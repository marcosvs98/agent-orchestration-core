from fastapi import APIRouter, Depends, Query, status
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
from domain.ai_policy.services.ai_service import AIService
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.error import ErrorResponse
from domain.governance.schemas.scopes import Scope
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context


class AIController:
    """HTTP controller for AI tasks and policies."""

    def __init__(self, service: AIService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["ai"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/ai-execution-policies",
            self.create_ai_execution_policy,
            methods=["POST"],
            response_model=AIExecutionPolicy,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/ai-execution-policy-versions",
            self.list_ai_execution_policy_versions,
            methods=["GET"],
            response_model=list[AIExecutionPolicyVersion],
        )
        r(
            "/ai-execution-policy-versions",
            self.create_ai_execution_policy_version,
            methods=["POST"],
            response_model=AIExecutionPolicyVersion,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:validate",
            self.validate_ai_execution_policy_version,
            methods=["POST"],
            response_model=AIExecutionPolicyVersion,
        )
        r(
            "/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:publish",
            self.publish_ai_execution_policy_version,
            methods=["POST"],
            response_model=AIExecutionPolicyVersion,
        )
        r(
            "/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:deprecate",
            self.deprecate_ai_execution_policy_version,
            methods=["POST"],
            response_model=AIExecutionPolicyVersion,
        )
        r(
            "/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:disable",
            self.disable_ai_execution_policy_version,
            methods=["POST"],
            response_model=AIExecutionPolicyVersion,
        )
        r(
            "/models",
            self.list_models,
            methods=["GET"],
            response_model=list[Model],
        )
        r(
            "/models",
            self.create_model,
            methods=["POST"],
            response_model=Model,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/node-ai-execution-policy-bindings",
            self.create_node_ai_execution_policy_binding,
            methods=["POST"],
            response_model=NodeAIExecutionPolicyBinding,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/node-ai-execution-policy-bindings",
            self.list_node_ai_execution_policy_bindings,
            methods=["GET"],
            response_model=list[NodeAIExecutionPolicyBinding],
        )
        r(
            "/node-ai-execution-policy-bindings/{binding_id}",
            self.delete_node_ai_execution_policy_binding,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    @staticmethod
    def _ensure_scope(auth: AuthContext, scope: Scope) -> None:
        if scope.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")

    async def create_ai_execution_policy(
        self,
        ai_execution_policy_create: AIExecutionPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicy:
        return await self.service.create_ai_execution_policy(
            tenant_id=auth.tenant_id,
            ai_execution_policy_create=ai_execution_policy_create,
            principal_id=auth.principal_id,
        )

    async def list_ai_execution_policy_versions(
        self,
        ai_execution_policy_id: str | None = Query(default=None),
        status_filter: list[str] | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[AIExecutionPolicyVersion]:
        return await self.service.list_ai_execution_policy_versions(
            tenant_id=auth.tenant_id,
            ai_execution_policy_id=ai_execution_policy_id,
            status_filter=status_filter,
            limit=limit,
        )

    async def create_ai_execution_policy_version(
        self,
        ai_execution_policy_version_create: AIExecutionPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        return await self.service.create_ai_execution_policy_version(
            tenant_id=auth.tenant_id,
            ai_execution_policy_version_create=ai_execution_policy_version_create,
            principal_id=auth.principal_id,
        )

    async def validate_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        return await self.service.validate_ai_execution_policy_version(
            tenant_id=auth.tenant_id,
            ai_execution_policy_id=ai_execution_policy_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            principal_id=auth.principal_id,
        )

    async def publish_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        return await self.service.publish_ai_execution_policy_version(
            tenant_id=auth.tenant_id,
            ai_execution_policy_id=ai_execution_policy_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def deprecate_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        return await self.service.deprecate_ai_execution_policy_version(
            tenant_id=auth.tenant_id,
            ai_execution_policy_id=ai_execution_policy_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def disable_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        return await self.service.disable_ai_execution_policy_version(
            tenant_id=auth.tenant_id,
            ai_execution_policy_id=ai_execution_policy_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def list_models(
        self, auth: AuthContext = Depends(get_auth_context)
    ) -> list[Model]:
        return await self.service.list_models()

    async def create_model(
        self,
        model_create: ModelCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> Model:
        self._ensure_scope(auth, Scope.ModelsCreate)
        return await self.service.create_model(model_create=model_create)

    async def create_node_ai_execution_policy_binding(
        self,
        node_ai_execution_policy_binding_create: NodeAIExecutionPolicyBindingCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> NodeAIExecutionPolicyBinding:
        self._ensure_scope(auth, Scope.NodeAIExecutionPolicyBindingsCreate)
        return await self.service.create_node_ai_execution_policy_binding(
            node_ai_execution_policy_binding_create=node_ai_execution_policy_binding_create
        )

    async def list_node_ai_execution_policy_bindings(
        self,
        node_id: UUID | None = Query(default=None),
        ai_execution_policy_version_id: UUID | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[NodeAIExecutionPolicyBinding]:
        self._ensure_scope(auth, Scope.NodeAIExecutionPolicyBindingsList)
        return await self.service.list_node_ai_execution_policy_bindings(
            node_id=node_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            limit=limit,
        )

    async def delete_node_ai_execution_policy_binding(
        self,
        binding_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        self._ensure_scope(auth, Scope.NodeAIExecutionPolicyBindingsDelete)
        await self.service.delete_node_ai_execution_policy_binding(
            binding_id=binding_id
        )
