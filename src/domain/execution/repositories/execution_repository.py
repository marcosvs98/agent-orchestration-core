from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import aliased

from infra.database.models.conversation.session import Session as SessionModel
from exceptions.service_exceptions import DomainValidationException, NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.execution.flow_run import FlowRun as FlowRunModel
from infra.database.models.execution.tool_run import ToolRun as ToolRunModel
from infra.database.models.execution.agent_run import AgentRun as AgentRunModel
from infra.database.models.execution.flow_run_lock import FlowRunLock as FlowRunLockModel
from infra.database.models.execution.execution_event import ExecutionEvent as ExecutionEventModel
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
from infra.database.models.flow.flow_graph_snapshot import FlowGraphSnapshot as FlowGraphSnapshotModel
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel
from infra.database.models.conversation.interaction import Interaction as InteractionModel
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
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def create_flow_run(
        self,
        *,
        session_id: UUID,
        flow_version_id: UUID,
        correlation_id: UUID,
        origin_flow_run_id: UUID | None,
        input_payload: dict,
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
        async with self.db.get_session() as session:
            session.add(
                FlowRunModel(
                    flow_run_id=flow_run_id,
                    session_id=session_id,
                    flow_version_id=flow_version_id,
                    correlation_id=correlation_id,
                    origin_flow_run_id=origin_flow_run_id,
                    input=input_payload,
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

    async def set_root_observation_id(self, *, flow_run_id: UUID, root_observation_id: str) -> None:
        async with self.db.get_session() as session:
            await session.execute(
                sa.update(FlowRunModel)
                .where(FlowRunModel.flow_run_id == flow_run_id)
                .values(root_observation_id=root_observation_id)
            )
            await session.commit()

    async def get_session(self, session_id: UUID) -> SessionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.session_id == session_id)
            )
            return result.scalar_one_or_none()

    async def get_flow_context(self, flow_run_id: UUID) -> tuple[UUID, UUID]:
        flow_run = await self.get_flow_run(flow_run_id)
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        session_record = await self.get_session(flow_run.session_id)
        if session_record is None:
            raise NotFoundServiceException(message="session_not_found")
        return flow_run.session_id, session_record.tenant_id

    async def next_event_sequence(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            await session.execute(
                select(FlowRunLockModel)
                .where(FlowRunLockModel.flow_run_id == flow_run_id)
                .with_for_update()
            )
            result = await session.execute(
                select(sa.func.coalesce(sa.func.max(ExecutionEventModel.event_sequence), 0)).where(
                    ExecutionEventModel.flow_run_id == flow_run_id
                )
            )
            current = result.scalar_one()
            return int(current) + 1

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
        async with self.db.get_session() as session:
            await session.execute(
                select(FlowRunLockModel)
                .where(FlowRunLockModel.flow_run_id == flow_run_id)
                .with_for_update()
            )
            result = await session.execute(
                select(sa.func.coalesce(sa.func.max(ExecutionEventModel.event_sequence), 0)).where(
                    ExecutionEventModel.flow_run_id == flow_run_id
                )
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
        async with self.db.get_session() as session:
            session.add(
                InteractionModel(
                    interaction_id=interaction_id,
                    session_id=session_id,
                    channel=channel,
                    payload=payload,
                    headers=headers,
                    metadata=metadata,
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
            result = await session.execute(
                select(InteractionModel).where(
                    InteractionModel.interaction_id == interaction_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="interaction_not_found")
            instance.flow_run_id = flow_run_id
            await session.commit()

    async def get_flow_run(self, flow_run_id: UUID) -> FlowRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowRunModel).where(FlowRunModel.flow_run_id == flow_run_id)
            )
            return result.scalar_one_or_none()

    async def get_tool_run(self, tool_run_id: UUID) -> ToolRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
            )
            return result.scalar_one_or_none()

    async def get_active_billing_policy_version_id(self, tenant_id: UUID) -> UUID | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveBillingPolicyVersionModel.billing_policy_version_id).where(
                    ActiveBillingPolicyVersionModel.tenant_id == tenant_id
                )
            )
            return result.scalar_one_or_none()

    async def get_billing_policy_version(
        self, billing_policy_version_id: UUID
    ) -> BillingPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(BillingPolicyVersionModel).where(
                    BillingPolicyVersionModel.billing_policy_version_id == billing_policy_version_id
                )
            )
            return result.scalar_one_or_none()

    async def stamp_agent_run_billing_policy(
        self, *, agent_run_id: UUID, billing_policy_version_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentRunModel).where(AgentRunModel.agent_run_id == agent_run_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            await session.commit()

    async def stamp_tool_run_billing_policy(
        self,
        *,
        tool_run_id: UUID,
        billing_policy_version_id: UUID,
        estimated_cost: float | None = None,
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            if estimated_cost is not None:
                instance.estimated_cost = estimated_cost
            await session.commit()

    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
    ) -> list[ExecutionEventModel]:
        async with self.db.get_session() as session:
            stmt = select(ExecutionEventModel)
            if flow_run_id is not None:
                stmt = stmt.where(ExecutionEventModel.flow_run_id == flow_run_id)
            if correlation_id is not None:
                stmt = stmt.where(ExecutionEventModel.correlation_id == correlation_id)
            stmt = stmt.order_by(ExecutionEventModel.flow_run_id, ExecutionEventModel.event_sequence).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_tool_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            node_run_direct = aliased(NodeRunModel)
            node_run_via_agent = aliased(NodeRunModel)
            stmt = (
                select(sa.func.count(sa.distinct(ToolRunModel.tool_run_id)))
                .select_from(ToolRunModel)
                .outerjoin(node_run_direct, ToolRunModel.node_run_id == node_run_direct.node_run_id)
                .outerjoin(AgentRunModel, ToolRunModel.agent_run_id == AgentRunModel.agent_run_id)
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
            return int(result.scalar_one() or 0)

    async def count_agent_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            stmt = (
                select(sa.func.count(sa.distinct(AgentRunModel.agent_run_id)))
                .select_from(AgentRunModel)
                .join(NodeRunModel, AgentRunModel.node_run_id == NodeRunModel.node_run_id)
                .where(NodeRunModel.flow_run_id == flow_run_id)
            )
            result = await session.execute(stmt)
            return int(result.scalar_one() or 0)

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
            result = await session.execute(
                select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.status = status
            instance.canonical_status = str(canonical_status)
            instance.output = output or {}
            instance.error = error or {}
            if status in {"COMPLETED", "FAILED"}:
                instance.finished_at = sa.func.now()
            await session.commit()

    async def get_flow_run_id_for_tool_run(self, tool_run_id: UUID) -> UUID:
        tool_run = await self.get_tool_run(tool_run_id)
        if tool_run is None:
            raise NotFoundServiceException(message="tool_run_not_found")

        if tool_run.node_run_id:
            node_run = await self.get_node_run(tool_run.node_run_id)
            if node_run is None:
                raise NotFoundServiceException(message="node_run_not_found")
            return node_run.flow_run_id

        if tool_run.agent_run_id:
            agent_run = await self.get_agent_run(tool_run.agent_run_id)
            if agent_run is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            node_run = await self.get_node_run(agent_run.node_run_id)
            if node_run is None:
                raise NotFoundServiceException(message="node_run_not_found")
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
        flow_run_id = await self.get_flow_run_id_for_tool_run(tool_run_id)
        flow_run = await self.get_flow_run(flow_run_id)
        if flow_run is None or flow_run.interaction_id is None:
            raise DomainValidationException(message="flow_run_missing_interaction")

        response_artifact_id = uuid4()
        async with self.db.get_session() as session:
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

    async def upsert_graph_state(
        self,
        *,
        flow_run_id: UUID,
        state: dict,
        last_node_run_id: UUID | None,
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(GraphStateModel).where(GraphStateModel.flow_run_id == flow_run_id)
            )
            instance = result.scalar_one_or_none()
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
            await session.commit()

    async def get_flow_version(self, flow_version_id: UUID) -> FlowVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowVersionModel).where(FlowVersionModel.flow_version_id == flow_version_id)
            )
            return result.scalar_one_or_none()

    async def get_flow(self, flow_id: UUID) -> FlowModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(select(FlowModel).where(FlowModel.flow_id == flow_id))
            return result.scalar_one_or_none()

    async def get_active_flow_version_id(self, flow_id: UUID) -> UUID | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveFlowVersionModel).where(ActiveFlowVersionModel.flow_id == flow_id)
            )
            row = result.scalar_one_or_none()
            return row.flow_version_id if row else None

    async def get_flow_graph_by_flow_version(self, flow_version_id: UUID) -> FlowGraphModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphModel).where(FlowGraphModel.flow_version_id == flow_version_id)
            )
            return result.scalar_one_or_none()

    async def get_flow_graph_snapshot_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphSnapshotModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphSnapshotModel).where(
                    FlowGraphSnapshotModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def get_tool_config(self, tool_config_id: UUID) -> ToolConfigModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolConfigModel).where(ToolConfigModel.tool_config_id == tool_config_id)
            )
            return result.scalar_one_or_none()

    async def get_agent_run(self, agent_run_id: UUID) -> AgentRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentRunModel).where(AgentRunModel.agent_run_id == agent_run_id)
            )
            return result.scalar_one_or_none()

    async def get_agent_version(self, agent_version_id: UUID) -> AgentVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentVersionModel).where(AgentVersionModel.agent_version_id == agent_version_id)
            )
            return result.scalar_one_or_none()

    async def get_active_agent_version_id(self, agent_id: UUID) -> UUID | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveAgentVersionModel).where(ActiveAgentVersionModel.agent_id == agent_id)
            )
            row = result.scalar_one_or_none()
            return row.agent_version_id if row else None

    async def get_ai_execution_policy_version(
        self, ai_execution_policy_version_id: UUID
    ) -> AIExecutionPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AIExecutionPolicyVersionModel).where(
                    AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                    == ai_execution_policy_version_id
                )
            )
            return result.scalar_one_or_none()

    async def get_model(self, model_id: UUID) -> ModelModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ModelModel).where(ModelModel.model_id == model_id)
            )
            return result.scalar_one_or_none()

    async def get_node_run(self, node_run_id: UUID) -> NodeRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(NodeRunModel).where(NodeRunModel.node_run_id == node_run_id)
            )
            return result.scalar_one_or_none()

    async def get_node(self, node_id: UUID) -> NodeModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(NodeModel).where(NodeModel.node_id == node_id)
            )
            return result.scalar_one_or_none()

    async def get_ai_task(self, ai_task_id: UUID) -> AITaskModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AITaskModel).where(AITaskModel.ai_task_id == ai_task_id)
            )
            return result.scalar_one_or_none()

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
    ) -> UUID:
        agent_run_id = uuid4()
        async with self.db.get_session() as session:
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
            result = await session.execute(
                select(AgentRunModel).where(AgentRunModel.agent_run_id == agent_run_id)
            )
            instance = result.scalar_one_or_none()
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
            await session.commit()

    async def acquire_flow_run_lock(
        self, flow_run_id: UUID, owner: str | None, correlation_id: UUID | None
    ) -> bool:
        async with self.db.get_session() as session:
            await session.execute(
                select(FlowRunLockModel)
                .where(FlowRunLockModel.flow_run_id == flow_run_id)
                .with_for_update()
            )
            existing = await session.execute(
                select(FlowRunLockModel).where(FlowRunLockModel.flow_run_id == flow_run_id)
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
