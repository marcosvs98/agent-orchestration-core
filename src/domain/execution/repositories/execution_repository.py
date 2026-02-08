from uuid import UUID, uuid4
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import aliased

from domain.execution.schemas.execution import FlowRunInput
from infra.database.models.conversation.session import Session as SessionModel
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
from infra.database.models.execution.flow_run import FlowRun as FlowRunModel
from infra.database.models.execution.tool_run import ToolRun as ToolRunModel
from infra.database.models.execution.agent_run import AgentRun as AgentRunModel
from infra.database.models.execution.flow_run_lock import (
    FlowRunLock as FlowRunLockModel,
)
from infra.database.models.execution.execution_event import (
    ExecutionEvent as ExecutionEventModel,
)
from infra.database.models.execution.node_run import NodeRun as NodeRunModel
from infra.database.models.execution.run_failure import RunFailure as RunFailureModel
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.ai_policy.ai_task import AITask as AITaskModel
from infra.database.models.ai_policy.execution_policy_version import (
    AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
)
from infra.database.models.ai_policy.model import Model as ModelModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.agent.active_agent_version import (
    ActiveAgentVersion as ActiveAgentVersionModel,
)
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.active_flow_version import (
    ActiveFlowVersion as ActiveFlowVersionModel,
)
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel
from infra.database.models.flow.flow_graph_snapshot import (
    FlowGraphSnapshot as FlowGraphSnapshotModel,
)
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel
from infra.database.models.conversation.interaction import (
    Interaction as InteractionModel,
)
from infra.database.models.conversation.response_artifact import (
    ResponseArtifact as ResponseArtifactModel,
)
from infra.database.models.governance.active_billing_policy_version import (
    ActiveBillingPolicyVersion as ActiveBillingPolicyVersionModel,
)
from infra.database.models.governance.billing_policy_version import (
    BillingPolicyVersion as BillingPolicyVersionModel,
)
from infra.database.models.execution.graph_state import GraphState as GraphStateModel


class ExecutionRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def create_flow_run(
        self,
        *,
        session_id: UUID,
        flow_version_id: UUID,
        correlation_id: UUID,
        origin_flow_run_id: UUID | None,
        input_payload: FlowRunInput,
        interaction_id: UUID | None = None,
        flow_graph_snapshot_id: UUID | None = None,
        execution_plan_hash: str | None = None,
        runtime_policy_hash: str | None = None,
        tool_catalog_hash: str | None = None,
        llm_provider_config_hash: str | None = None,
        trace_id: UUID | None = None,
        root_observation_id: str | None = None,
    ) -> UUID:
        flow_run_id = uuid4()
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.create_flow_run",
            input={
                "flow_run_id": str(flow_run_id),
                "flow_version_id": str(flow_version_id),
                "session_id": str(session_id),
            },
        ):
            async with self.db.get_session() as session:
                session.add(
                    FlowRunModel(
                        flow_run_id=flow_run_id,
                        session_id=session_id,
                        flow_version_id=flow_version_id,
                        correlation_id=correlation_id,
                        origin_flow_run_id=origin_flow_run_id,
                        input=input_payload.model_dump(mode="json"),
                        interaction_id=interaction_id,
                        flow_graph_snapshot_id=flow_graph_snapshot_id,
                        execution_plan_hash=execution_plan_hash,
                        runtime_policy_hash=runtime_policy_hash,
                        tool_catalog_hash=tool_catalog_hash,
                        llm_provider_config_hash=llm_provider_config_hash,
                        trace_id=trace_id,
                        root_observation_id=root_observation_id,
                    )
                )
                session.add(
                    FlowRunLockModel(
                        flow_run_id=flow_run_id,
                        locked_at=sa.func.now(),
                        owner=None,
                        correlation_id=correlation_id,
                    )
                )
                await session.commit()
        return flow_run_id

    async def set_root_observation_id(
        self, *, flow_run_id: UUID, root_observation_id: str
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_root_observation_id",
            input={"flow_run_id": str(flow_run_id)},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(root_observation_id=root_observation_id)
                )
                await session.commit()

    async def complete_flow_run(
        self,
        *,
        flow_run_id: UUID,
        status: str,
        output: dict,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.complete_flow_run",
            input={"flow_run_id": str(flow_run_id), "status": status},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status=status,
                        canonical_status=status,
                        output=output,
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    async def fail_flow_run(
        self,
        *,
        flow_run_id: UUID,
        failure_reason: str,
        error: dict | None = None,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.fail_flow_run",
            input={"flow_run_id": str(flow_run_id), "reason": failure_reason},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status="FAILED",
                        canonical_status="FAILED",
                        error=error or {"reason": failure_reason},
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    async def set_flow_run_status(
        self,
        *,
        flow_run_id: UUID,
        status: str,
        canonical_status: str,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_flow_run_status",
            input={"flow_run_id": str(flow_run_id), "status": status},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status=status,
                        canonical_status=canonical_status,
                    )
                )
                await session.commit()

    async def set_flow_run_output(
        self,
        *,
        flow_run_id: UUID,
        output: dict,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_flow_run_output",
            input={"flow_run_id": str(flow_run_id)},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(output=output or {})
                )
                await session.commit()

    async def get_session(self, session_id: UUID) -> SessionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_session",
            input={"session_id": str(session_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(SessionModel).where(SessionModel.session_id == session_id)
                )
                session_record = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": session_record is not None})
                return session_record

    async def create_session(self, *, session_id: UUID, tenant_id: UUID) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_session_for_create",
                input={"session_id": str(session_id)},
            ) as handle:
                existing = await session.execute(
                    select(SessionModel).where(SessionModel.session_id == session_id)
                )
                existing_record = existing.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": existing_record is not None})
            if existing_record is None:
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.execution.repository.create_session",
                    input={"session_id": str(session_id), "tenant_id": str(tenant_id)},
                ):
                    session.add(
                        SessionModel(session_id=session_id, tenant_id=tenant_id)
                    )
                    await session.commit()

    async def get_flow_context(self, flow_run_id: UUID) -> tuple[UUID, UUID]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_context",
            input={"flow_run_id": str(flow_run_id)},
        ) as handle:
            flow_run = await self.get_flow_run(flow_run_id)
            if flow_run is None:
                raise NotFoundServiceException(message="flow_run_not_found")
            session_record = await self.get_session(flow_run.session_id)
            if session_record is None:
                raise NotFoundServiceException(message="session_not_found")
            if handle:
                handle.success(
                    output={
                        "session_id": str(flow_run.session_id),
                        "tenant_id": str(session_record.tenant_id),
                    }
                )
            return flow_run.session_id, session_record.tenant_id

    async def next_event_sequence(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.acquire_event_lock",
                input={"flow_run_id": str(flow_run_id)},
            ):
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_event_sequence",
                input={"flow_run_id": str(flow_run_id)},
            ) as handle:
                result = await session.execute(
                    select(
                        sa.func.coalesce(
                            sa.func.max(ExecutionEventModel.event_sequence), 0
                        )
                    ).where(ExecutionEventModel.flow_run_id == flow_run_id)
                )
                current = result.scalar_one()
                next_seq = int(current) + 1
                if handle:
                    handle.success(output={"next_sequence": next_seq})
                return next_seq

    async def append_execution_event(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        event_type: str,
        payload: dict,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        schema_version: int = 1,
        node_id: UUID | None = None,
        edge_id: str | None = None,
    ) -> UUID:
        event_id = uuid4()
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.append_execution_event",
            input={
                "flow_run_id": str(flow_run_id),
                "event_type": event_type,
                "correlation_id": str(correlation_id),
            },
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
                result = await session.execute(
                    select(
                        sa.func.coalesce(
                            sa.func.max(ExecutionEventModel.event_sequence), 0
                        )
                    ).where(ExecutionEventModel.flow_run_id == flow_run_id)
                )
                next_seq = int(result.scalar_one()) + 1
                session.add(
                    ExecutionEventModel(
                        execution_event_id=event_id,
                        tenant_id=tenant_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        causation_id=causation_id,
                        event_sequence=next_seq,
                        schema_version=schema_version,
                        type=event_type,
                        payload=payload,
                        node_id=node_id,
                        edge_id=edge_id,
                    )
                )
                await session.commit()
        return event_id

    async def create_interaction(
        self,
        *,
        session_id: UUID,
        channel: str,
        payload: dict,
        headers: dict,
        metadata: dict,
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> UUID:
        interaction_id = uuid4()
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.create_interaction",
            input={
                "interaction_id": str(interaction_id),
                "session_id": str(session_id),
            },
        ):
            async with self.db.get_session() as session:
                session.add(
                    InteractionModel(
                        interaction_id=interaction_id,
                        session_id=session_id,
                        channel=channel,
                        payload=payload,
                        output={},
                        headers=headers,
                        interaction_metadata=metadata,
                        result_node_run_id=None,
                        external_message_id=external_message_id,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                await session.commit()
        return interaction_id

    async def link_interaction_to_flow_run(
        self, *, interaction_id: UUID, flow_run_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_interaction_for_link",
                input={"interaction_id": str(interaction_id)},
            ) as handle:
                result = await session.execute(
                    select(InteractionModel).where(
                        InteractionModel.interaction_id == interaction_id
                    )
                )
                instance = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="interaction_not_found")
            instance.flow_run_id = flow_run_id
            await session.execute(
                sa.update(FlowRunModel)
                .where(FlowRunModel.flow_run_id == flow_run_id)
                .values(interaction_id=interaction_id)
            )
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.link_interaction_to_flow_run",
                input={
                    "interaction_id": str(interaction_id),
                    "flow_run_id": str(flow_run_id),
                },
            ):
                await session.commit()

    async def set_current_interaction_result_for_flow_run(
        self,
        *,
        flow_run_id: UUID,
        output: dict,
        result_node_run_id: UUID | None,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_current_interaction_result_for_flow_run",
            input={"flow_run_id": str(flow_run_id)},
        ):
            async with self.db.get_session() as session:
                interaction_id_subq = (
                    select(FlowRunModel.interaction_id)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .scalar_subquery()
                )
                await session.execute(
                    sa.update(InteractionModel)
                    .where(InteractionModel.interaction_id == interaction_id_subq)
                    .values(
                        output=output or {},
                        result_node_run_id=result_node_run_id,
                    )
                )
                await session.commit()

    async def get_flow_run(self, flow_run_id: UUID) -> FlowRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(FlowRunModel).where(FlowRunModel.flow_run_id == flow_run_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow_run",
                input={
                    "query": query_sql,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "get_flow_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                flow_run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow_run else 0,
                            "found": flow_run is not None,
                        }
                    )

                return flow_run

    async def get_tool_run(self, tool_run_id: UUID) -> ToolRunModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_tool_run",
            input={"tool_run_id": str(tool_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
                )
                tool_run = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": tool_run is not None})
                return tool_run

    async def get_active_billing_policy_version_id(
        self, tenant_id: UUID
    ) -> UUID | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_active_billing_policy_version_id",
            input={"tenant_id": str(tenant_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(
                        ActiveBillingPolicyVersionModel.billing_policy_version_id
                    ).where(ActiveBillingPolicyVersionModel.tenant_id == tenant_id)
                )
                row = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": row is not None})
                return row

    async def get_billing_policy_version(
        self, billing_policy_version_id: UUID
    ) -> BillingPolicyVersionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_billing_policy_version",
            input={"billing_policy_version_id": str(billing_policy_version_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(BillingPolicyVersionModel).where(
                        BillingPolicyVersionModel.billing_policy_version_id
                        == billing_policy_version_id
                    )
                )
                policy = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": policy is not None})
                return policy

    async def stamp_agent_run_billing_policy(
        self, *, agent_run_id: UUID, billing_policy_version_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run_for_billing",
                input={"agent_run_id": str(agent_run_id)},
            ) as h:
                result = await session.execute(
                    select(AgentRunModel).where(
                        AgentRunModel.agent_run_id == agent_run_id
                    )
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.stamp_agent_run_billing_policy",
                input={
                    "agent_run_id": str(agent_run_id),
                    "billing_policy_version_id": str(billing_policy_version_id),
                },
            ):
                await session.commit()

    async def stamp_tool_run_billing_policy(
        self,
        *,
        tool_run_id: UUID,
        billing_policy_version_id: UUID,
        estimated_cost: float | None = None,
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_run_for_billing",
                input={"tool_run_id": str(tool_run_id)},
            ) as h:
                result = await session.execute(
                    select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            if estimated_cost is not None:
                instance.estimated_cost = estimated_cost
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.stamp_tool_run_billing_policy",
                input={
                    "tool_run_id": str(tool_run_id),
                    "billing_policy_version_id": str(billing_policy_version_id),
                },
            ):
                await session.commit()

    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
    ) -> list[ExecutionEventModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.list_execution_events",
            input={
                "flow_run_id": str(flow_run_id) if flow_run_id else None,
                "correlation_id": str(correlation_id) if correlation_id else None,
                "limit": limit,
            },
        ) as handle:
            async with self.db.get_session() as session:
                stmt = select(ExecutionEventModel)
                if flow_run_id is not None:
                    stmt = stmt.where(ExecutionEventModel.flow_run_id == flow_run_id)
                if correlation_id is not None:
                    stmt = stmt.where(
                        ExecutionEventModel.correlation_id == correlation_id
                    )
                stmt = stmt.order_by(
                    ExecutionEventModel.flow_run_id,
                    ExecutionEventModel.event_sequence,
                ).limit(limit)
                result = await session.execute(stmt)
                events = list(result.scalars().all())
                if handle:
                    handle.success(output={"count": len(events)})
                return events

    async def count_tool_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.count_tool_runs_for_flow_run",
            input={"flow_run_id": str(flow_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                node_run_direct = aliased(NodeRunModel)
                node_run_via_agent = aliased(NodeRunModel)
                stmt = (
                    select(sa.func.count(sa.distinct(ToolRunModel.tool_run_id)))
                    .select_from(ToolRunModel)
                    .outerjoin(
                        node_run_direct,
                        ToolRunModel.node_run_id == node_run_direct.node_run_id,
                    )
                    .outerjoin(
                        AgentRunModel,
                        ToolRunModel.agent_run_id == AgentRunModel.agent_run_id,
                    )
                    .outerjoin(
                        node_run_via_agent,
                        AgentRunModel.node_run_id == node_run_via_agent.node_run_id,
                    )
                    .where(
                        sa.or_(
                            node_run_direct.flow_run_id == flow_run_id,
                            node_run_via_agent.flow_run_id == flow_run_id,
                        )
                    )
                )
                result = await session.execute(stmt)
                count = int(result.scalar_one() or 0)
                if handle:
                    handle.success(output={"count": count})
                return count

    async def count_agent_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.count_agent_runs_for_flow_run",
            input={"flow_run_id": str(flow_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                stmt = (
                    select(sa.func.count(sa.distinct(AgentRunModel.agent_run_id)))
                    .select_from(AgentRunModel)
                    .join(
                        NodeRunModel,
                        AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                    )
                    .where(NodeRunModel.flow_run_id == flow_run_id)
                )
                result = await session.execute(stmt)
                count = int(result.scalar_one() or 0)
                if handle:
                    handle.success(output={"count": count})
                return count

    async def update_tool_run_result(
        self,
        *,
        tool_run_id: UUID,
        status: str,
        canonical_status: str,
        output: dict | None,
        error: dict | None,
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_run_for_result",
                input={"tool_run_id": str(tool_run_id)},
            ) as h:
                result = await session.execute(
                    select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.status = status
            instance.canonical_status = str(canonical_status)
            instance.output = output or {}
            instance.error = error or {}
            if status in {"COMPLETED", "FAILED"}:
                instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_tool_run_result",
                input={"tool_run_id": str(tool_run_id), "status": status},
            ):
                await session.commit()

    async def get_flow_run_id_for_tool_run(self, tool_run_id: UUID) -> UUID:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_run_id_for_tool_run",
            input={"tool_run_id": str(tool_run_id)},
        ) as handle:
            tool_run = await self.get_tool_run(tool_run_id)
            if tool_run is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            if tool_run.node_run_id:
                node_run = await self.get_node_run(tool_run.node_run_id)
                if node_run is None:
                    raise NotFoundServiceException(message="node_run_not_found")
                if handle:
                    handle.success(output={"flow_run_id": str(node_run.flow_run_id)})
                return node_run.flow_run_id
            if tool_run.agent_run_id:
                agent_run = await self.get_agent_run(tool_run.agent_run_id)
                if agent_run is None:
                    raise NotFoundServiceException(message="agent_run_not_found")
                node_run = await self.get_node_run(agent_run.node_run_id)
                if node_run is None:
                    raise NotFoundServiceException(message="node_run_not_found")
                if handle:
                    handle.success(output={"flow_run_id": str(node_run.flow_run_id)})
                return node_run.flow_run_id
            raise DomainValidationException(message="tool_run_missing_parent")

    async def create_run_failure_for_tool_run(
        self,
        *,
        tool_run_id: UUID,
        correlation_id: UUID,
        error_type: str,
        error: dict,
    ) -> UUID:
        run_failure_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_run_failure_for_tool_run",
                input={
                    "tool_run_id": str(tool_run_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    RunFailureModel(
                        run_failure_id=run_failure_id,
                        tool_run_id=tool_run_id,
                        error_type=error_type,
                        error=error,
                        correlation_id=correlation_id,
                    )
                )
            await session.commit()
        return run_failure_id

    async def create_response_artifact_for_tool_run(
        self, *, tool_run_id: UUID, payload: dict
    ) -> UUID:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_run_for_artifact",
            input={"tool_run_id": str(tool_run_id)},
        ) as handle:
            flow_run_id = await self.get_flow_run_id_for_tool_run(tool_run_id)
            flow_run = await self.get_flow_run(flow_run_id)
            if handle:
                handle.success(
                    output={
                        "flow_run_id": str(flow_run_id),
                        "found": flow_run is not None,
                    }
                )
        if flow_run is None or flow_run.interaction_id is None:
            raise DomainValidationException(message="flow_run_missing_interaction")

        response_artifact_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_response_artifact",
                input={
                    "tool_run_id": str(tool_run_id),
                    "flow_run_id": str(flow_run_id),
                },
            ):
                session.add(
                    ResponseArtifactModel(
                        response_artifact_id=response_artifact_id,
                        interaction_id=flow_run.interaction_id,
                        flow_run_id=flow_run_id,
                        payload=payload,
                        schema_version=1,
                    )
                )
            await session.commit()
        return response_artifact_id

    async def create_tool_run(
        self,
        *,
        tool_config_id: UUID,
        correlation_id: UUID,
        agent_run_id: UUID | None,
        node_run_id: UUID | None,
        idempotency_key: str | None,
        has_side_effect: bool,
        input_payload: dict,
        estimated_cost: float | None = None,
        billing_policy_version_id: UUID | None = None,
    ) -> UUID:
        tool_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_tool_run",
                input={
                    "tool_config_id": str(tool_config_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    ToolRunModel(
                        tool_run_id=tool_run_id,
                        tool_config_id=tool_config_id,
                        correlation_id=correlation_id,
                        agent_run_id=agent_run_id,
                        node_run_id=node_run_id,
                        idempotency_key=idempotency_key,
                        has_side_effect=has_side_effect,
                        input=input_payload,
                        estimated_cost=estimated_cost,
                        billing_policy_version_id=billing_policy_version_id,
                    )
                )
            await session.commit()
        return tool_run_id

    async def create_node_run(
        self,
        *,
        flow_run_id: UUID,
        node_id: UUID,
        correlation_id: UUID,
        input_payload: dict,
        output_payload: dict,
        status: str,
        canonical_status: str,
    ) -> UUID:
        node_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_node_run",
                input={
                    "flow_run_id": str(flow_run_id),
                    "node_id": str(node_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    NodeRunModel(
                        node_run_id=node_run_id,
                        flow_run_id=flow_run_id,
                        node_id=node_id,
                        correlation_id=correlation_id,
                        input=input_payload,
                        output=output_payload,
                        status=status,
                        canonical_status=canonical_status,
                    )
                )
            await session.commit()
        return node_run_id

    async def update_node_run_result(
        self,
        *,
        node_run_id: UUID,
        output_payload: dict,
        status: str,
        canonical_status: str,
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_node_run_for_result",
                input={"node_run_id": str(node_run_id)},
            ) as h:
                result = await session.execute(
                    select(NodeRunModel).where(NodeRunModel.node_run_id == node_run_id)
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="node_run_not_found")
            instance.output = output_payload
            instance.status = status
            instance.canonical_status = canonical_status
            instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_node_run_result",
                input={"node_run_id": str(node_run_id), "status": status},
            ):
                await session.commit()

    async def get_graph_state(self, flow_run_id: UUID) -> GraphStateModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_graph_state",
            input={"flow_run_id": str(flow_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(GraphStateModel).where(
                        GraphStateModel.flow_run_id == flow_run_id
                    )
                )
                state = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": state is not None})
                return state

    async def upsert_graph_state(
        self,
        *,
        flow_run_id: UUID,
        state: dict,
        last_node_run_id: UUID | None,
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_graph_state_for_upsert",
                input={"flow_run_id": str(flow_run_id)},
            ) as h:
                result = await session.execute(
                    select(GraphStateModel).where(
                        GraphStateModel.flow_run_id == flow_run_id
                    )
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                session.add(
                    GraphStateModel(
                        flow_run_id=flow_run_id,
                        state=state,
                        last_node_run_id=last_node_run_id,
                    )
                )
            else:
                instance.state = state
                instance.last_node_run_id = last_node_run_id
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.upsert_graph_state",
                input={"flow_run_id": str(flow_run_id)},
            ):
                await session.commit()

    async def get_flow_version(self, flow_version_id: UUID) -> FlowVersionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_version",
            input={"flow_version_id": str(flow_version_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(FlowVersionModel).where(
                        FlowVersionModel.flow_version_id == flow_version_id
                    )
                )
                version = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": version is not None})
                return version

    async def get_flow(self, flow_id: UUID) -> FlowModel | None:
        async with self.db.get_session() as session:
            stmt = select(FlowModel).where(FlowModel.flow_id == flow_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow",
                input={"query": query_sql, "params": {"flow_id": str(flow_id)}},
                metadata={"retriever_name": "get_flow"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                flow = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow else 0,
                            "found": flow is not None,
                        }
                    )

                return flow

    async def get_active_flow_version_id(self, flow_id: UUID) -> UUID | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_active_flow_version_id",
            input={"flow_id": str(flow_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(ActiveFlowVersionModel).where(
                        ActiveFlowVersionModel.flow_id == flow_id
                    )
                )
                row = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": row is not None})
                return row.flow_version_id if row else None

    async def get_flow_graph_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_graph_by_flow_version",
            input={"flow_version_id": str(flow_version_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(FlowGraphModel).where(
                        FlowGraphModel.flow_version_id == flow_version_id
                    )
                )
                graph = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": graph is not None})
                return graph

    async def get_flow_graph_snapshot_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphSnapshotModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_graph_snapshot",
            input={"flow_version_id": str(flow_version_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(FlowGraphSnapshotModel).where(
                        FlowGraphSnapshotModel.flow_version_id == flow_version_id
                    )
                )
                snapshot = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": snapshot is not None})
                return snapshot

    async def get_tool_config(self, tool_config_id: UUID) -> ToolConfigModel | None:
        async with self.db.get_session() as session:
            stmt = select(ToolConfigModel).where(
                ToolConfigModel.tool_config_id == tool_config_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_config",
                input={
                    "query": query_sql,
                    "params": {"tool_config_id": str(tool_config_id)},
                },
                metadata={"retriever_name": "get_tool_config"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                tool_config = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if tool_config else 0,
                            "found": tool_config is not None,
                        }
                    )

                return tool_config

    async def get_agent_run(self, agent_run_id: UUID) -> AgentRunModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_agent_run",
            input={"agent_run_id": str(agent_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AgentRunModel).where(
                        AgentRunModel.agent_run_id == agent_run_id
                    )
                )
                run = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": run is not None})
                return run

    async def get_agent_run_by_agent_version_and_flow(
        self, agent_version_id: UUID, flow_run_id: UUID
    ) -> AgentRunModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_agent_run_by_version_and_flow",
            input={
                "agent_version_id": str(agent_version_id),
                "flow_run_id": str(flow_run_id),
            },
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AgentRunModel)
                    .join(
                        NodeRunModel,
                        AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                    )
                    .where(
                        AgentRunModel.agent_version_id == agent_version_id,
                        NodeRunModel.flow_run_id == flow_run_id,
                    )
                    .order_by(AgentRunModel.created_at.desc())
                )
                run = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": run is not None})
                return run

    async def get_agent_version(
        self, agent_version_id: UUID
    ) -> AgentVersionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_agent_version",
            input={"agent_version_id": str(agent_version_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AgentVersionModel).where(
                        AgentVersionModel.agent_version_id == agent_version_id
                    )
                )
                version = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": version is not None})
                return version

    async def get_active_agent_version_id(self, agent_id: UUID) -> UUID | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_active_agent_version_id",
            input={"agent_id": str(agent_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(ActiveAgentVersionModel).where(
                        ActiveAgentVersionModel.agent_id == agent_id
                    )
                )
                row = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": row is not None})
                return row.agent_version_id if row else None

    async def get_ai_execution_policy_version(
        self, ai_execution_policy_version_id: UUID
    ) -> AIExecutionPolicyVersionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_ai_execution_policy_version",
            input={
                "ai_execution_policy_version_id": str(ai_execution_policy_version_id),
            },
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AIExecutionPolicyVersionModel).where(
                        AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                        == ai_execution_policy_version_id
                    )
                )
                policy = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": policy is not None})
                return policy

    async def get_model(self, model_id: UUID) -> ModelModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_model",
            input={"model_id": str(model_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(ModelModel).where(ModelModel.model_id == model_id)
                )
                model = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": model is not None})
                return model

    async def get_node_run(self, node_run_id: UUID) -> NodeRunModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_node_run",
            input={"node_run_id": str(node_run_id)},
        ) as handle:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(NodeRunModel).where(NodeRunModel.node_run_id == node_run_id)
                )
                run = result.scalar_one_or_none()
                if handle:
                    handle.success(output={"found": run is not None})
                return run

    async def get_node(self, node_id: UUID) -> NodeModel | None:
        async with self.db.get_session() as session:
            stmt = select(NodeModel).where(NodeModel.node_id == node_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_node",
                input={"query": query_sql, "params": {"node_id": str(node_id)}},
                metadata={"retriever_name": "get_node"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                node = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if node else 0,
                            "found": node is not None,
                        }
                    )

                return node

    async def get_ai_task(self, ai_task_id: UUID) -> AITaskModel | None:
        async with self.db.get_session() as session:
            stmt = select(AITaskModel).where(AITaskModel.ai_task_id == ai_task_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_ai_task",
                input={
                    "query": query_sql,
                    "params": {"ai_task_id": str(ai_task_id)},
                },
                metadata={"retriever_name": "get_ai_task"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                ai_task = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if ai_task else 0,
                            "found": ai_task is not None,
                        }
                    )

                return ai_task

    async def create_agent_run(
        self,
        *,
        ai_task_id: UUID | None,
        node_run_id: UUID,
        agent_version_id: UUID,
        ai_execution_policy_version_id: UUID,
        correlation_id: UUID,
        input_payload: dict,
        model: str | None,
        billing_policy_version_id: UUID | None = None,
        system_prompt_hash: str | None = None,
    ) -> UUID:
        agent_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_agent_run",
                input={
                    "node_run_id": str(node_run_id),
                    "agent_version_id": str(agent_version_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    AgentRunModel(
                        agent_run_id=agent_run_id,
                        ai_task_id=ai_task_id,
                        node_run_id=node_run_id,
                        agent_version_id=agent_version_id,
                        ai_execution_policy_version_id=ai_execution_policy_version_id,
                        correlation_id=correlation_id,
                        input=input_payload,
                        model=model,
                        billing_policy_version_id=billing_policy_version_id,
                        system_prompt_hash=system_prompt_hash,
                    )
                )
            await session.commit()
        return agent_run_id

    async def update_agent_run_result(
        self,
        *,
        agent_run_id: UUID,
        status: str,
        canonical_status: str,
        output: dict | None,
        error: dict | None,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost: float | None,
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run_for_result",
                input={"agent_run_id": str(agent_run_id)},
            ) as h:
                result = await session.execute(
                    select(AgentRunModel).where(
                        AgentRunModel.agent_run_id == agent_run_id
                    )
                )
                instance = result.scalar_one_or_none()
                if h:
                    h.success(output={"found": instance is not None})
            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.status = status
            instance.canonical_status = canonical_status
            instance.output = output or {}
            instance.error = error or {}
            instance.output_tokens = output_tokens
            instance.input_tokens = input_tokens
            instance.estimated_cost = estimated_cost
            instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_agent_run_result",
                input={"agent_run_id": str(agent_run_id), "status": status},
            ):
                await session.commit()

    async def acquire_flow_run_lock(
        self, flow_run_id: UUID, owner: str | None, correlation_id: UUID | None
    ) -> bool:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.acquire_flow_run_lock",
                input={"flow_run_id": str(flow_run_id)},
            ):
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
                existing = await session.execute(
                    select(FlowRunLockModel).where(
                        FlowRunLockModel.flow_run_id == flow_run_id
                    )
                )
                lock = existing.scalar_one_or_none()
                if lock is None:
                    session.add(
                        FlowRunLockModel(
                            flow_run_id=flow_run_id,
                            locked_at=sa.func.now(),
                            owner=owner,
                            correlation_id=correlation_id,
                        )
                    )
                await session.commit()
        return True

    async def list_node_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[NodeRunModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.list_node_runs",
            input={
                "tenant_id": str(tenant_id),
                "flow_run_id": str(flow_run_id) if flow_run_id else None,
                "limit": limit,
            },
        ) as handle:
            async with self.db.get_session() as session:
                stmt = (
                    select(NodeRunModel)
                    .join(
                        FlowRunModel,
                        NodeRunModel.flow_run_id == FlowRunModel.flow_run_id,
                    )
                    .join(
                        SessionModel,
                        FlowRunModel.session_id == SessionModel.session_id,
                    )
                    .where(SessionModel.tenant_id == tenant_id)
                )
                if flow_run_id is not None:
                    stmt = stmt.where(NodeRunModel.flow_run_id == flow_run_id)
                stmt = stmt.order_by(NodeRunModel.created_at.desc()).limit(limit)
                result = await session.execute(stmt)
                runs = list(result.scalars().all())
                if handle:
                    handle.success(output={"count": len(runs)})
                return runs

    async def list_agent_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRunModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.list_agent_runs",
            input={
                "tenant_id": str(tenant_id),
                "flow_run_id": str(flow_run_id) if flow_run_id else None,
                "limit": limit,
            },
        ) as handle:
            async with self.db.get_session() as session:
                stmt = (
                    select(AgentRunModel)
                    .join(
                        NodeRunModel,
                        AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                    )
                    .join(
                        FlowRunModel,
                        NodeRunModel.flow_run_id == FlowRunModel.flow_run_id,
                    )
                    .join(
                        SessionModel,
                        FlowRunModel.session_id == SessionModel.session_id,
                    )
                    .where(SessionModel.tenant_id == tenant_id)
                )
                if flow_run_id is not None:
                    stmt = stmt.where(FlowRunModel.flow_run_id == flow_run_id)
                stmt = stmt.order_by(AgentRunModel.created_at.desc()).limit(limit)
                result = await session.execute(stmt)
                runs = list(result.scalars().all())
                if handle:
                    handle.success(output={"count": len(runs)})
                return runs
