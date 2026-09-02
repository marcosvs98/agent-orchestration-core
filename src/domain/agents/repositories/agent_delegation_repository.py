from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.execution.agent_delegation import (
    AgentDelegation as AgentDelegationModel,
)


class AgentDelegationRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def create_delegation(
        self,
        *,
        tenant_id: UUID,
        parent_agent_run_id: UUID,
        target_agent_id: UUID | None,
        transport: str,
        remote_endpoint: str | None,
        a2a_task_id: str,
        a2a_context_id: str,
        a2a_task_state: str,
        request_message: dict,
        correlation_id: UUID,
    ) -> UUID:
        agent_delegation_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.a2a.repository.create_delegation",
                input={
                    "parent_agent_run_id": str(parent_agent_run_id),
                    "a2a_task_id": a2a_task_id,
                    "transport": transport,
                },
            ):
                session.add(
                    AgentDelegationModel(
                        agent_delegation_id=agent_delegation_id,
                        tenant_id=tenant_id,
                        parent_agent_run_id=parent_agent_run_id,
                        target_agent_id=target_agent_id,
                        transport=transport,
                        remote_endpoint=remote_endpoint,
                        a2a_task_id=a2a_task_id,
                        a2a_context_id=a2a_context_id,
                        a2a_task_state=a2a_task_state,
                        request_message=request_message,
                        correlation_id=correlation_id,
                        started_at=datetime.now(timezone.utc),
                    )
                )
            await session.commit()
        return agent_delegation_id

    async def update_delegation_result(
        self,
        *,
        agent_delegation_id: UUID,
        a2a_task_state: str,
        child_agent_run_id: UUID | None,
        result: dict,
        error: dict,
        finished: bool,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = select(AgentDelegationModel).where(
                AgentDelegationModel.agent_delegation_id == agent_delegation_id
            )
            instance = (await session.execute(stmt)).scalar_one_or_none()
            if instance is None:
                return
            instance.a2a_task_state = a2a_task_state
            instance.child_agent_run_id = child_agent_run_id
            instance.result = result
            instance.error = error
            if finished:
                instance.finished_at = datetime.now(timezone.utc)
            await session.commit()

    async def get_delegation_by_task_id(
        self, *, tenant_id: UUID, a2a_task_id: str
    ) -> AgentDelegationModel | None:
        async with self.db.get_session() as session:
            stmt = select(AgentDelegationModel).where(
                AgentDelegationModel.tenant_id == tenant_id,
                AgentDelegationModel.a2a_task_id == a2a_task_id,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def list_delegations_for_agent_run(
        self, *, parent_agent_run_id: UUID
    ) -> list[AgentDelegationModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentDelegationModel)
                .where(AgentDelegationModel.parent_agent_run_id == parent_agent_run_id)
                .order_by(AgentDelegationModel.created_at)
            )
            return list((await session.execute(stmt)).scalars().all())
