from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.conversation.schemas.continuity import ConversationSummaryRecord
from infra.database import DatabaseConnection
from infra.database.models.conversation.conversation_summary import (
    ConversationSummary as ConversationSummaryModel,
)


class ConversationSummaryRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get(self, *, conversation_key: str) -> ConversationSummaryRecord | None:
        async with self.db.get_session() as session:
            stmt = select(ConversationSummaryModel).where(
                ConversationSummaryModel.conversation_key == conversation_key
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return ConversationSummaryRecord(
                tenant_id=row.tenant_id,
                conversation_key=row.conversation_key,
                summary_text=row.summary_text,
                turns_covered=int(row.turns_covered),
                estimated_tokens_covered=int(row.estimated_tokens_covered),
                provider_conversation_id=row.provider_conversation_id,
                rollover_count=int(row.rollover_count),
            )

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        conversation_key: str,
        session_id: UUID | None,
        summary_text: str,
        turns_covered: int,
        estimated_tokens_covered: int,
        provider_conversation_id: str | None,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                pg_insert(ConversationSummaryModel)
                .values(
                    tenant_id=tenant_id,
                    conversation_key=conversation_key,
                    session_id=session_id,
                    summary_text=summary_text,
                    turns_covered=turns_covered,
                    estimated_tokens_covered=estimated_tokens_covered,
                    provider_conversation_id=provider_conversation_id,
                    rollover_count=1,
                    last_rolled_over_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_update(
                    index_elements=[ConversationSummaryModel.conversation_key],
                    set_={
                        "summary_text": summary_text,
                        "turns_covered": turns_covered,
                        "estimated_tokens_covered": estimated_tokens_covered,
                        "provider_conversation_id": provider_conversation_id,
                        "rollover_count": ConversationSummaryModel.rollover_count + 1,
                        "last_rolled_over_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def set_provider_conversation_id(
        self, *, conversation_key: str, provider_conversation_id: str
    ) -> None:
        async with self.db.get_session() as session:
            stmt = select(ConversationSummaryModel).where(
                ConversationSummaryModel.conversation_key == conversation_key
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return
            row.provider_conversation_id = provider_conversation_id
            session.add(row)
            await session.commit()
