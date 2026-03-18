from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.human_sla.schemas.sla_case import (
    SLACaseCreate,
    SLAResolutionStatus,
    SLAStatus,
)
from infra.database import DatabaseConnection
from infra.database.models.escalation.sla_case import SLACase


class HumanSLARepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def create_case(self, case_create: SLACaseCreate) -> SLACase | None:
        async with self.db.get_session() as session:
            stmt = (
                pg_insert(SLACase)
                .values(case_create.model_dump())
                .on_conflict_do_nothing(
                    constraint="uq_sla_case_flow_run_node_run",
                )
                .returning(SLACase.sla_case_id)
            )
            result = await session.execute(stmt)
            inserted_sla_case_id = result.scalar_one_or_none()
            await session.commit()
            if inserted_sla_case_id is None:
                return None
            query = select(SLACase).where(SLACase.sla_case_id == inserted_sla_case_id)
            created_result = await session.execute(query)
            return created_result.scalar_one()

    async def get_case(self, sla_case_id: UUID, tenant_id: UUID) -> SLACase | None:
        async with self.db.get_session() as session:
            stmt = select(SLACase).where(
                SLACase.sla_case_id == sla_case_id,
                SLACase.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_cases(
        self,
        tenant_id: UUID,
        status: SLAStatus | None,
        limit: int,
        offset: int,
    ) -> list[SLACase]:
        async with self.db.get_session() as session:
            stmt = (
                select(SLACase)
                .where(SLACase.tenant_id == tenant_id)
                .order_by(SLACase.opened_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if status is not None:
                stmt = stmt.where(SLACase.status == status.value)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_cases_by_session(
        self, tenant_id: UUID, session_id: UUID
    ) -> list[SLACase]:
        async with self.db.get_session() as session:
            stmt = (
                select(SLACase)
                .where(
                    SLACase.tenant_id == tenant_id,
                    SLACase.session_id == session_id,
                )
                .order_by(SLACase.opened_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_last_open_case_for_session(
        self, tenant_id: UUID, session_id: UUID
    ) -> SLACase | None:
        async with self.db.get_session() as session:
            stmt = (
                select(SLACase)
                .where(
                    SLACase.tenant_id == tenant_id,
                    SLACase.session_id == session_id,
                    SLACase.status == SLAStatus.OPEN.value,
                )
                .order_by(SLACase.opened_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def assign_case(
        self, tenant_id: UUID, sla_case_id: UUID, human_agent_id: str
    ) -> SLACase | None:
        async with self.db.get_session() as session:
            stmt = (
                update(SLACase)
                .where(
                    SLACase.sla_case_id == sla_case_id,
                    SLACase.tenant_id == tenant_id,
                )
                .values(
                    human_agent_id=human_agent_id,
                    status=SLAStatus.ASSIGNED.value,
                    assigned_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.commit()
            query = select(SLACase).where(
                SLACase.sla_case_id == sla_case_id,
                SLACase.tenant_id == tenant_id,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def resolve_case(
        self,
        tenant_id: UUID,
        sla_case_id: UUID,
        resolution_status: SLAResolutionStatus,
        resolution_summary: str,
        human_agent_id: str,
    ) -> SLACase | None:
        async with self.db.get_session() as session:
            stmt = (
                update(SLACase)
                .where(
                    SLACase.sla_case_id == sla_case_id,
                    SLACase.tenant_id == tenant_id,
                )
                .values(
                    status=SLAStatus.RESOLVED.value,
                    resolution_status=resolution_status.value,
                    resolution_summary=resolution_summary,
                    human_agent_id=human_agent_id,
                    resolved_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.commit()
            query = select(SLACase).where(
                SLACase.sla_case_id == sla_case_id,
                SLACase.tenant_id == tenant_id,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def update_case_escalation(
        self,
        sla_case_id: UUID,
        tenant_id: UUID,
        priority: str,
        level: int,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                update(SLACase)
                .where(
                    SLACase.sla_case_id == sla_case_id,
                    SLACase.tenant_id == tenant_id,
                )
                .values(priority=priority, current_escalation_level=level)
            )
            await session.execute(stmt)
            await session.commit()

    async def update_case_sla_breached(
        self, sla_case_id: UUID, tenant_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                update(SLACase)
                .where(
                    SLACase.sla_case_id == sla_case_id,
                    SLACase.tenant_id == tenant_id,
                )
                .values(sla_breached=True)
            )
            await session.execute(stmt)
            await session.commit()
