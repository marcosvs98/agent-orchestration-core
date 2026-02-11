from __future__ import annotations

from uuid import UUID, uuid4
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database.models.execution.flow_run import FlowRun
from infra.database.models.execution.node_run import NodeRun
from infra.database.models.execution.agent_run import AgentRun
from infra.database.models.execution.execution_event import ExecutionEvent
from infra.database.models.execution.run_failure import RunFailure
from resources.scripts.validation_seed import BILLING_POLICY_VERSION_ID


async def create_flow_run(
    session: AsyncSession,
    *,
    session_id: UUID,
    flow_version_id: UUID,
    correlation_id: UUID,
    user_id: str = "test-user",
    origin_flow_run_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> UUID:
    """Insert a FlowRun row and return its id."""
    flow_run_id = uuid4()
    session.add(
        FlowRun(
            flow_run_id=flow_run_id,
            session_id=session_id,
            flow_version_id=flow_version_id,
            correlation_id=correlation_id,
            user_id=user_id,
            origin_flow_run_id=origin_flow_run_id,
            input=payload or {},
        )
    )
    await session.flush()
    return flow_run_id


async def append_execution_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: str = "test-user",
    session_id: UUID,
    flow_run_id: UUID,
    correlation_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    causation_id: UUID | None = None,
    event_sequence: int | None = None,
) -> UUID:
    """Append an execution event with the next sequence number."""
    event_id = uuid4()

    if event_sequence is None:
        await session.flush()
        result = await session.execute(
            sa.select(sa.func.coalesce(sa.func.max(ExecutionEvent.event_sequence), 0)).where(
                ExecutionEvent.flow_run_id == flow_run_id
            )
        )
        next_sequence = int(result.scalar_one()) + 1
    else:
        next_sequence = event_sequence

    session.add(
        ExecutionEvent(
            execution_event_id=event_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            event_sequence=next_sequence,
            schema_version=1,
            type=event_type,
            payload=payload,
        )
    )
    await session.flush()
    return event_id


async def create_node_run(
    session: AsyncSession,
    *,
    flow_run_id: UUID,
    node_id: UUID,
    correlation_id: UUID,
    status: str,
    canonical_status: str,
) -> UUID:
    """Insert a NodeRun row."""
    node_run_id = uuid4()
    session.add(
        NodeRun(
            node_run_id=node_run_id,
            flow_run_id=flow_run_id,
            node_id=node_id,
            status=status,
            canonical_status=canonical_status,
            correlation_id=correlation_id,
        )
    )
    await session.flush()
    return node_run_id


async def create_agent_run(
    session: AsyncSession,
    *,
    node_run_id: UUID,
    agent_version_id: UUID,
    ai_execution_policy_version_id: UUID,
    correlation_id: UUID,
    estimated_cost: float | None = None,
    status: str = "CREATED",
    canonical_status: str = "CREATED",
    billing_policy_version_id: UUID | None = BILLING_POLICY_VERSION_ID,
) -> UUID:
    """Insert an AgentRun row and return its id."""
    agent_run_id = uuid4()
    session.add(
        AgentRun(
            agent_run_id=agent_run_id,
            node_run_id=node_run_id,
            agent_version_id=agent_version_id,
            ai_execution_policy_version_id=ai_execution_policy_version_id,
            correlation_id=correlation_id,
            estimated_cost=estimated_cost,
            status=status,
            canonical_status=canonical_status,
            input={},
            output={},
            error={},
            billing_policy_version_id=billing_policy_version_id,
        )
    )
    await session.flush()
    return agent_run_id


async def create_run_failure(
    session: AsyncSession,
    *,
    tool_run_id: UUID | None,
    correlation_id: UUID,
    error_type: str,
    error: dict[str, Any],
) -> UUID:
    """Insert a RunFailure row."""
    run_failure_id = uuid4()
    session.add(
        RunFailure(
            run_failure_id=run_failure_id,
            tool_run_id=tool_run_id,
            correlation_id=correlation_id,
            error=error,
            error_type=error_type,
        )
    )
    await session.flush()
    return run_failure_id
