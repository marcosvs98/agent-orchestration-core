from __future__ import annotations

from typing import Any
from uuid import UUID

from adapters.observability.logging import get_logger
from domain.conversation.repositories.conversation_read_repository import (
    ConversationReadRepository,
)
from domain.conversation.schemas.conversation_read import (
    EndUserDetailResponse,
    EndUserListItem,
    InteractionReadRecord,
    InteractionSummary,
    PaginatedEndUsersResponse,
    PaginatedInteractionsResponse,
    PaginatedSessionsResponse,
    SessionSummary,
)
from domain.execution.repositories.execution_repository import ExecutionRepository
from exceptions.service_exceptions import NotFoundServiceException

logger = get_logger(__name__)


def _interaction_user_input(payload: dict[str, Any] | None) -> Any | None:
    if not payload:
        return None
    inp = payload.get("input")
    if not isinstance(inp, dict):
        return None
    return inp.get("user_input")


def _interaction_system_output(output: dict[str, Any] | None) -> str | None:
    if not output:
        return None
    v = output.get("system_output")
    if v is None:
        return None
    return v if isinstance(v, str) else str(v)


def _to_interaction_summary(r: InteractionReadRecord) -> InteractionSummary:
    return InteractionSummary(
        interaction_id=r.interaction_id,
        session_id=r.session_id,
        flow_run_id=r.flow_run_id,
        result_node_run_id=r.result_node_run_id,
        channel=r.channel,
        received_at=r.received_at,
        completed_at=r.completed_at,
        external_message_id=r.external_message_id,
        request_id=r.request_id,
        trace_id=r.trace_id,
        user_input=_interaction_user_input(r.payload),
        system_output=_interaction_system_output(r.output),
    )


class ConversationReadService:
    def __init__(
        self,
        read_repository: ConversationReadRepository,
        execution_repository: ExecutionRepository,
    ) -> None:
        self.read_repository = read_repository
        self.execution_repository = execution_repository

    async def list_interactions(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: str | None,
        limit: int,
        offset: int,
    ) -> PaginatedInteractionsResponse:
        if session_id is not None:
            rows, has_next = await self.read_repository.list_interactions_by_session(
                tenant_id=tenant_id,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
        else:
            rows, has_next = await self.read_repository.list_interactions_by_user(
                tenant_id=tenant_id,
                user_id=user_id or "",
                limit=limit,
                offset=offset,
            )
        items = [_to_interaction_summary(r) for r in rows]
        return PaginatedInteractionsResponse(
            items=items, limit=limit, offset=offset, has_next=has_next
        )

    async def list_sessions(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None,
        limit: int,
        offset: int,
    ) -> PaginatedSessionsResponse:
        rows, has_next = await self.read_repository.list_sessions(
            tenant_id=tenant_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        logger.info(
            "Listed sessions",
            tenant_id=str(tenant_id),
            user_filter=user_id is not None,
            result_count=len(rows),
            has_next=has_next,
        )
        return PaginatedSessionsResponse(
            items=[SessionSummary(session_id=r.session_id, user_id=r.user_id) for r in rows],
            limit=limit,
            offset=offset,
            has_next=has_next,
        )

    async def list_end_users(
        self, *, tenant_id: UUID, limit: int, offset: int
    ) -> PaginatedEndUsersResponse:
        rows, has_next = await self.read_repository.list_end_users(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
        logger.info(
            "Listed end users",
            tenant_id=str(tenant_id),
            result_count=len(rows),
            has_next=has_next,
        )
        return PaginatedEndUsersResponse(
            items=[
                EndUserListItem(end_user_id=r.end_user_id, user_id=r.user_id) for r in rows
            ],
            limit=limit,
            offset=offset,
            has_next=has_next,
        )

    async def get_end_user_detail(
        self, *, tenant_id: UUID, user_id: str
    ) -> EndUserDetailResponse:
        end_user_id = await self.read_repository.get_end_user_id(
            tenant_id=tenant_id, user_id=user_id
        )
        if end_user_id is None:
            raise NotFoundServiceException(message="end_user_not_found")
        preferences = await self.execution_repository.get_user_preferences(
            tenant_id=tenant_id, user_id=user_id
        )
        memory_profile = await self.execution_repository.get_user_memory_profile(
            tenant_id=tenant_id, user_id=user_id
        )
        logger.info(
            "Fetched end user detail",
            tenant_id=str(tenant_id),
            end_user_id=str(end_user_id),
        )
        return EndUserDetailResponse(
            end_user_id=end_user_id,
            user_id=user_id,
            preferences=preferences,
            memory_profile=memory_profile,
        )
