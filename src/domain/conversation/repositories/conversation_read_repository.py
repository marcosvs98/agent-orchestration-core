from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from domain.conversation.schemas.conversation_read import (
    EndUserReadRecord,
    InteractionReadRecord,
    SessionReadRecord,
)
from infra.database import DatabaseConnection
from infra.database.models.conversation.interaction import (
    Interaction as InteractionModel,
)
from infra.database.models.conversation.session import Session as SessionModel
from infra.database.models.conversation.user import User as EndUserModel


class ConversationReadRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def list_interactions_by_session(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[InteractionReadRecord], bool]:
        cols = [
            InteractionModel.interaction_id,
            InteractionModel.session_id,
            InteractionModel.flow_run_id,
            InteractionModel.result_node_run_id,
            InteractionModel.channel,
            InteractionModel.received_at,
            InteractionModel.completed_at,
            InteractionModel.external_message_id,
            InteractionModel.request_id,
            InteractionModel.trace_id,
            InteractionModel.payload,
            InteractionModel.output,
        ]
        async with self.db.get_session() as session:
            base = (
                select(*cols)
                .select_from(InteractionModel)
                .join(
                    SessionModel,
                    InteractionModel.session_id == SessionModel.session_id,
                )
                .where(
                    SessionModel.tenant_id == tenant_id,
                    InteractionModel.session_id == session_id,
                )
                .order_by(
                    InteractionModel.received_at.desc(),
                    InteractionModel.interaction_id.desc(),
                )
            )
            result = await session.execute(base.limit(limit + 1).offset(offset))
            raw = result.all()
            has_next = len(raw) > limit
            raw = raw[:limit]
            rows = [
                InteractionReadRecord(
                    interaction_id=r[0],
                    session_id=r[1],
                    flow_run_id=r[2],
                    result_node_run_id=r[3],
                    channel=r[4],
                    received_at=r[5],
                    completed_at=r[6],
                    external_message_id=r[7],
                    request_id=r[8],
                    trace_id=r[9],
                    payload=r[10] if isinstance(r[10], dict) else {},
                    output=r[11] if isinstance(r[11], dict) else {},
                    headers=None,
                )
                for r in raw
            ]
            return rows, has_next

    async def list_interactions_by_user(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list[InteractionReadRecord], bool]:
        cols = [
            InteractionModel.interaction_id,
            InteractionModel.session_id,
            InteractionModel.flow_run_id,
            InteractionModel.result_node_run_id,
            InteractionModel.channel,
            InteractionModel.received_at,
            InteractionModel.completed_at,
            InteractionModel.external_message_id,
            InteractionModel.request_id,
            InteractionModel.trace_id,
            InteractionModel.payload,
            InteractionModel.output,
        ]
        async with self.db.get_session() as session:
            base = (
                select(*cols)
                .select_from(InteractionModel)
                .join(
                    SessionModel,
                    InteractionModel.session_id == SessionModel.session_id,
                )
                .where(
                    SessionModel.tenant_id == tenant_id,
                    SessionModel.user_id == user_id,
                )
                .order_by(
                    InteractionModel.received_at.desc(),
                    InteractionModel.interaction_id.desc(),
                )
            )
            result = await session.execute(base.limit(limit + 1).offset(offset))
            raw = result.all()
            has_next = len(raw) > limit
            raw = raw[:limit]
            rows = [
                InteractionReadRecord(
                    interaction_id=r[0],
                    session_id=r[1],
                    flow_run_id=r[2],
                    result_node_run_id=r[3],
                    channel=r[4],
                    received_at=r[5],
                    completed_at=r[6],
                    external_message_id=r[7],
                    request_id=r[8],
                    trace_id=r[9],
                    payload=r[10] if isinstance(r[10], dict) else {},
                    output=r[11] if isinstance(r[11], dict) else {},
                    headers=None,
                )
                for r in raw
            ]
            return rows, has_next

    async def list_sessions(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SessionReadRecord], bool]:
        async with self.db.get_session() as session:
            stmt = select(SessionModel.session_id, SessionModel.user_id).where(
                SessionModel.tenant_id == tenant_id
            )
            if user_id is not None:
                stmt = stmt.where(SessionModel.user_id == user_id)
            stmt = (
                stmt.order_by(SessionModel.session_id.desc())
                .limit(limit + 1)
                .offset(offset)
            )
            result = await session.execute(stmt)
            raw = result.all()
            has_next = len(raw) > limit
            raw = raw[:limit]
            return (
                [SessionReadRecord(session_id=r[0], user_id=r[1]) for r in raw],
                has_next,
            )

    async def list_end_users(
        self,
        *,
        tenant_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[EndUserReadRecord], bool]:
        async with self.db.get_session() as session:
            stmt = (
                select(EndUserModel.end_user_id, EndUserModel.user_id)
                .where(EndUserModel.tenant_id == tenant_id)
                .order_by(EndUserModel.end_user_id.desc())
                .limit(limit + 1)
                .offset(offset)
            )
            result = await session.execute(stmt)
            raw = result.all()
            has_next = len(raw) > limit
            raw = raw[:limit]
            return (
                [EndUserReadRecord(end_user_id=r[0], user_id=r[1]) for r in raw],
                has_next,
            )

    async def get_end_user_id(self, *, tenant_id: UUID, user_id: str) -> UUID | None:
        async with self.db.get_session() as session:
            stmt = select(EndUserModel.end_user_id).where(
                EndUserModel.tenant_id == tenant_id,
                EndUserModel.user_id == user_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
