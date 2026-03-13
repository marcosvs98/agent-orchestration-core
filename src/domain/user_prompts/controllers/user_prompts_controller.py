from uuid import UUID

from fastapi import APIRouter, Depends, status

from domain.common.schemas.error import ErrorResponse
from domain.user_prompts.schemas.user_prompts import UserPrompt, UserPromptCreate
from domain.user_prompts.services.user_prompts_service import UserPromptsService
from utils.auth import AuthContext, get_auth_context


class UserPromptsController:
    def __init__(self, service: UserPromptsService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["user-prompts"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/user-prompts",
            self.list_user_prompts,
            methods=["GET"],
            response_model=list[UserPrompt],
            responses=self._resp405(),
        )
        r(
            "/user-prompts",
            self.create_user_prompt,
            methods=["POST"],
            response_model=UserPrompt,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/user-prompts/{user_prompt_id}",
            self.get_user_prompt,
            methods=["GET"],
            response_model=UserPrompt,
            responses=self._resp405(),
        )
        r(
            "/user-prompts/{user_prompt_id}",
            self.delete_user_prompt,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            responses=self._resp405(),
        )

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_user_prompts(
        self,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[UserPrompt]:
        return await self.service.list_user_prompts(tenant_id=auth.tenant_id)

    async def create_user_prompt(
        self,
        create: UserPromptCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> UserPrompt:
        return await self.service.create_user_prompt(
            tenant_id=auth.tenant_id,
            create=create,
            principal_id=auth.principal_id,
        )

    async def get_user_prompt(
        self,
        user_prompt_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> UserPrompt:
        return await self.service.get_user_prompt(
            tenant_id=auth.tenant_id,
            user_prompt_id=user_prompt_id,
        )

    async def delete_user_prompt(
        self,
        user_prompt_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        await self.service.deactivate_user_prompt(
            tenant_id=auth.tenant_id,
            user_prompt_id=user_prompt_id,
        )
