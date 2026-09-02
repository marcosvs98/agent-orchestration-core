from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import select

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.agent_run import AgentRunOrigin
from domain.execution.services.state_machine import AgentRunStatus, RunStatus
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.execution.agent_run import AgentRun as AgentRunModel
from infra.database.models.execution.agent_run_artifact import (
    AgentRunArtifact as AgentRunArtifactModel,
)
from infra.database.models.execution.agent_run_event import (
    AgentRunEvent as AgentRunEventModel,
)
from infra.database.models.execution.agent_run_message import (
    AgentRunMessage as AgentRunMessageModel,
)
from infra.database.models.execution.node_run import NodeRun as NodeRunModel
from infra.database.models.execution.tool_run import ToolRun as ToolRunModel


class AgentRunRepository:
    """Persistence for agent runs that are not owned by a flow node.

    Flow-embedded agent runs keep using ``ExecutionRepository``; the difference is only the
    parent and the event sink, so the ``agent_run`` row itself stays a single table.
    """

    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def create_agent_run(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID,
        agent_version_id: UUID,
        correlation_id: UUID,
        origin: AgentRunOrigin,
        input_payload: dict,
        context_snapshot: dict,
        tool_grant: dict,
        max_iterations: int,
        model: str | None,
        billing_policy_version_id: UUID | None,
        ai_execution_policy_version_id: UUID | None,
        system_prompt_hash: str | None,
        runtime_snapshot: dict,
        runtime_snapshot_hash: str | None,
        parent_agent_run_id: UUID | None = None,
        root_agent_run_id: UUID | None = None,
        delegation_depth: int = 0,
        idempotency_key: str | None = None,
    ) -> UUID:
        agent_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.agent_run_repository.create_agent_run",
                input={
                    "tenant_id": str(tenant_id),
                    "agent_id": str(agent_id),
                    "agent_version_id": str(agent_version_id),
                    "origin": origin.value,
                    "delegation_depth": delegation_depth,
                },
            ):
                session.add(
                    AgentRunModel(
                        agent_run_id=agent_run_id,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        agent_version_id=agent_version_id,
                        node_run_id=None,
                        correlation_id=correlation_id,
                        origin=origin.value,
                        parent_agent_run_id=parent_agent_run_id,
                        root_agent_run_id=root_agent_run_id or agent_run_id,
                        delegation_depth=delegation_depth,
                        input=input_payload,
                        output={},
                        error={},
                        context_snapshot=context_snapshot,
                        tool_grant=tool_grant,
                        max_iterations=max_iterations,
                        iterations_used=0,
                        model=model,
                        billing_policy_version_id=billing_policy_version_id,
                        ai_execution_policy_version_id=ai_execution_policy_version_id,
                        system_prompt_hash=system_prompt_hash,
                        runtime_snapshot=runtime_snapshot,
                        runtime_snapshot_hash=runtime_snapshot_hash,
                        idempotency_key=idempotency_key,
                        status=RunStatus.CREATED.value,
                        canonical_status=AgentRunStatus.CREATED.value,
                    )
                )
            await session.commit()
        return agent_run_id

    async def get_agent_run(self, *, tenant_id: UUID, agent_run_id: UUID) -> AgentRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(AgentRunModel).where(
                AgentRunModel.agent_run_id == agent_run_id,
                AgentRunModel.tenant_id == tenant_id,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def list_agent_runs(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        flow_run_id: UUID | None = None,
        root_agent_run_id: UUID | None = None,
        parent_agent_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRunModel]:
        async with self.db.get_session() as session:
            stmt = select(AgentRunModel).where(AgentRunModel.tenant_id == tenant_id)
            if agent_id is not None:
                stmt = stmt.where(AgentRunModel.agent_id == agent_id)
            if flow_run_id is not None:
                stmt = stmt.join(
                    NodeRunModel, AgentRunModel.node_run_id == NodeRunModel.node_run_id
                ).where(NodeRunModel.flow_run_id == flow_run_id)
            if root_agent_run_id is not None:
                stmt = stmt.where(AgentRunModel.root_agent_run_id == root_agent_run_id)
            if parent_agent_run_id is not None:
                stmt = stmt.where(AgentRunModel.parent_agent_run_id == parent_agent_run_id)
            stmt = stmt.order_by(AgentRunModel.created_at.desc()).limit(limit)
            return list((await session.execute(stmt)).scalars().all())

    async def mark_running(self, *, agent_run_id: UUID) -> None:
        async with self.db.get_session() as session:
            instance = await session.get(AgentRunModel, agent_run_id)
            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.status = RunStatus.RUNNING.value
            instance.canonical_status = AgentRunStatus.RUNNING.value
            instance.started_at = datetime.now(timezone.utc)
            await session.commit()

    async def finish_agent_run(
        self,
        *,
        agent_run_id: UUID,
        status: str,
        canonical_status: str,
        output: dict,
        error: dict,
        finish_reason: str | None,
        iterations_used: int,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost: float | None,
    ) -> None:
        async with self.db.get_session() as session:
            instance = await session.get(AgentRunModel, agent_run_id)
            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.status = status
            instance.canonical_status = canonical_status
            instance.output = output
            instance.error = error
            instance.finish_reason = finish_reason
            instance.iterations_used = iterations_used
            instance.input_tokens = input_tokens
            instance.output_tokens = output_tokens
            instance.estimated_cost = estimated_cost
            instance.finished_at = datetime.now(timezone.utc)
            await session.commit()

    async def append_message(
        self,
        *,
        agent_run_id: UUID,
        role: str,
        content: str | None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_calls: list[dict] | None = None,
        trust_level: str | None = None,
        source: str | None = None,
        provenance: dict | None = None,
    ) -> int:
        async with self.db.get_session() as session:
            next_sequence = await self._next_sequence(
                session,
                column=AgentRunMessageModel.message_sequence,
                model=AgentRunMessageModel,
                agent_run_id=agent_run_id,
            )
            session.add(
                AgentRunMessageModel(
                    agent_run_message_id=uuid4(),
                    agent_run_id=agent_run_id,
                    message_sequence=next_sequence,
                    role=role,
                    content=content,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_calls=tool_calls or [],
                    trust_level=trust_level,
                    source=source,
                    provenance=provenance or {},
                )
            )
            await session.commit()
        return next_sequence

    async def append_event(
        self,
        *,
        agent_run_id: UUID,
        tenant_id: UUID,
        event_type: str,
        payload: dict,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> int:
        async with self.db.get_session() as session:
            next_sequence = await self._next_sequence(
                session,
                column=AgentRunEventModel.event_sequence,
                model=AgentRunEventModel,
                agent_run_id=agent_run_id,
            )
            session.add(
                AgentRunEventModel(
                    agent_run_event_id=uuid4(),
                    agent_run_id=agent_run_id,
                    tenant_id=tenant_id,
                    type=event_type,
                    event_sequence=next_sequence,
                    occurred_at=datetime.now(timezone.utc),
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    schema_version=schema_version,
                    payload=payload,
                )
            )
            await session.commit()
        return next_sequence

    async def append_artifact(
        self,
        *,
        agent_run_id: UUID,
        name: str,
        description: str | None,
        parts: list[dict],
        payload: dict,
    ) -> int:
        async with self.db.get_session() as session:
            next_index = await self._next_sequence(
                session,
                column=AgentRunArtifactModel.artifact_index,
                model=AgentRunArtifactModel,
                agent_run_id=agent_run_id,
            )
            session.add(
                AgentRunArtifactModel(
                    agent_run_artifact_id=uuid4(),
                    agent_run_id=agent_run_id,
                    artifact_index=next_index,
                    name=name,
                    description=description,
                    parts=parts,
                    payload=payload,
                )
            )
            await session.commit()
        return next_index

    @staticmethod
    async def _next_sequence(session, *, column, model, agent_run_id: UUID) -> int:
        stmt = sa.select(sa.func.coalesce(sa.func.max(column), 0)).where(
            model.agent_run_id == agent_run_id
        )
        current = (await session.execute(stmt)).scalar_one()
        return int(current) + 1

    async def list_messages(self, *, agent_run_id: UUID) -> list[AgentRunMessageModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentRunMessageModel)
                .where(AgentRunMessageModel.agent_run_id == agent_run_id)
                .order_by(AgentRunMessageModel.message_sequence)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def list_events(self, *, agent_run_id: UUID) -> list[AgentRunEventModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentRunEventModel)
                .where(AgentRunEventModel.agent_run_id == agent_run_id)
                .order_by(AgentRunEventModel.event_sequence)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def list_artifacts(self, *, agent_run_id: UUID) -> list[AgentRunArtifactModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentRunArtifactModel)
                .where(AgentRunArtifactModel.agent_run_id == agent_run_id)
                .order_by(AgentRunArtifactModel.artifact_index)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def list_tool_runs(self, *, agent_run_id: UUID) -> list[ToolRunModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(ToolRunModel)
                .where(ToolRunModel.agent_run_id == agent_run_id)
                .order_by(ToolRunModel.created_at)
            )
            return list((await session.execute(stmt)).scalars().all())
