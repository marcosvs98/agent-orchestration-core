from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from domain.conversation.schemas.conversation_read import (
    EndUserDetailResponse,
    PaginatedEndUsersResponse,
    PaginatedInteractionsResponse,
    PaginatedSessionsResponse,
)
from domain.conversation.services.conversation_read_service import (
    ConversationReadService,
)
from utils.auth import AuthContext, get_auth_context


class ConversationReadController:
    def __init__(self, service: ConversationReadService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["conversation-read"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/interactions",
            self.list_interactions,
            methods=["GET"],
            response_model=PaginatedInteractionsResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/sessions",
            self.list_sessions,
            methods=["GET"],
            response_model=PaginatedSessionsResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/end-users",
            self.list_end_users,
            methods=["GET"],
            response_model=PaginatedEndUsersResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/end-users/{user_id}",
            self.get_end_user,
            methods=["GET"],
            response_model=EndUserDetailResponse,
            status_code=status.HTTP_200_OK,
        )

    async def list_interactions(
        self,
        session_id: UUID | None = Query(default=None),
        user_id: str | None = Query(default=None, max_length=255),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: AuthContext = Depends(get_auth_context),
    ) -> PaginatedInteractionsResponse:
        if (session_id is None) == (user_id is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "value_error",
                        "loc": ["query"],
                        "msg": "Exactly one of session_id or user_id must be provided.",
                    }
                ],
            )
        return await self.service.list_interactions(
            tenant_id=auth.tenant_id,
            session_id=session_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def list_sessions(
        self,
        user_id: str | None = Query(default=None, max_length=255),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: AuthContext = Depends(get_auth_context),
    ) -> PaginatedSessionsResponse:
        return await self.service.list_sessions(
            tenant_id=auth.tenant_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def list_end_users(
        self,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: AuthContext = Depends(get_auth_context),
    ) -> PaginatedEndUsersResponse:
        return await self.service.list_end_users(
            tenant_id=auth.tenant_id, limit=limit, offset=offset
        )

    async def get_end_user(
        self,
        user_id: str = Path(..., max_length=255),
        auth: AuthContext = Depends(get_auth_context),
    ) -> EndUserDetailResponse:
        return await self.service.get_end_user_detail(tenant_id=auth.tenant_id, user_id=user_id)
