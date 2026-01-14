from fastapi import APIRouter, Depends, status

from domain.ai_policy.schemas.ai import (
    AITask,
    AITaskCreate,
    AIExecutionPolicy,
    AIExecutionPolicyCreate,
    AIExecutionPolicyVersion,
    AIExecutionPolicyVersionCreate,
    Model,
)
from domain.ai_policy.services.ai_service import AIService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException
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
        r("/ai-tasks", self.list_ai_tasks, methods=["GET"], response_model=list[AITask], responses=self._resp405())
        r("/ai-execution-policies", self.create_ai_execution_policy, methods=["POST"], response_model=AIExecutionPolicy, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/ai-execution-policy-versions", self.list_ai_execution_policy_versions, methods=["GET"], response_model=list[AIExecutionPolicyVersion], responses=self._resp405())
        r("/ai-execution-policy-versions", self.create_ai_execution_policy_version, methods=["POST"], response_model=AIExecutionPolicyVersion, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:publish", self.publish_ai_execution_policy_version, methods=["POST"], response_model=AIExecutionPolicyVersion, responses=self._resp405())
        r("/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:deprecate", self.deprecate_ai_execution_policy_version, methods=["POST"], response_model=AIExecutionPolicyVersion, responses=self._resp405())
        r("/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:disable", self.disable_ai_execution_policy_version, methods=["POST"], response_model=AIExecutionPolicyVersion, responses=self._resp405())
        r("/models", self.list_models, methods=["GET"], response_model=list[Model], responses=self._resp405())

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_ai_tasks(self, _: AuthContext = Depends(get_auth_context)) -> list[AITask]:
        raise MethodNotAllowedPlaceholderException()

    async def create_ai_execution_policy(
        self, __: AIExecutionPolicyCreate, _: AuthContext = Depends(get_auth_context)
    ) -> AIExecutionPolicy:
        raise MethodNotAllowedPlaceholderException()

    async def list_ai_execution_policy_versions(
        self,
        status_filter: list[str] | None = None,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[AIExecutionPolicyVersion]:
        raise MethodNotAllowedPlaceholderException()

    async def create_ai_execution_policy_version(
        self,
        __: AIExecutionPolicyVersionCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        raise MethodNotAllowedPlaceholderException()

    async def publish_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        raise MethodNotAllowedPlaceholderException()

    async def deprecate_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        raise MethodNotAllowedPlaceholderException()

    async def disable_ai_execution_policy_version(
        self,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> AIExecutionPolicyVersion:
        raise MethodNotAllowedPlaceholderException()

    async def list_models(self, _: AuthContext = Depends(get_auth_context)) -> list[Model]:
        raise MethodNotAllowedPlaceholderException()
