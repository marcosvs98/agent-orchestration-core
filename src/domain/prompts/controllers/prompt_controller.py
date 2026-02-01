from __future__ import annotations

from fastapi import APIRouter, Depends, status

from domain.common.schemas.error import ErrorResponse
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException
from utils.auth import AuthContext, get_auth_context


class PromptController:
    """HTTP controller for node prompt management."""

    def __init__(self, service: PromptService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["prompts"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/nodes/{node_type}/prompt",
            self.get_prompt,
            methods=["GET"],
            response_model=NodePrompt,
            responses=self._resp405(),
        )
        r(
            "/nodes/{node_type}/prompt",
            self.create_or_update_prompt,
            methods=["POST"],
            response_model=NodePrompt,
            status_code=status.HTTP_200_OK,
            responses=self._resp405(),
        )
        r(
            "/nodes/{node_type}/prompt",
            self.delete_prompt,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            responses=self._resp405(),
        )

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def get_prompt(
        self,
        node_type: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> NodePrompt:
        prompt = await self.service.get_prompt(node_type)
        if not prompt:
            raise DomainValidationException(
                message="prompt_not_found",
                detail=f"Active prompt not found for node_type: {node_type}",
            )
        return prompt

    async def create_or_update_prompt(
        self,
        node_type: str,
        create: NodePromptCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> NodePrompt:
        if create.node_type != node_type:
            raise DomainValidationException(
                message="node_type_mismatch",
                detail="node_type in path must match node_type in body",
            )
        create.created_by = auth.principal_id
        return await self.service.create_or_update_prompt(
            create, tenant_id=auth.tenant_id
        )

    async def delete_prompt(
        self,
        node_type: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        await self.service.deactivate_prompt(node_type, tenant_id=auth.tenant_id)
