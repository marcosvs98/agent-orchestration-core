from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa

from infra.database.models.conversation.session import Session
from infra.database.models.execution.agent_run import AgentRun
from infra.database.models.execution.flow_run import FlowRun
from infra.database.models.execution.node_run import NodeRun
from resources.scripts.validation_seed import (
    AGENT_VERSION_ID,
    FLOW_VERSION_ID,
    NODE_ID,
    POLICY_VERSION_ID,
    SESSION_ID,
    TENANT_ID,
)
from .helpers import create_agent_run, create_flow_run, create_node_run
from .evidence import json_block, text_block, write_markdown

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_costs_aggregate_per_tenant_without_replay_duplication(db_session) -> None:
    correlation_id = uuid4()
    flow_run_id = await create_flow_run(
        db_session,
        session_id=SESSION_ID,
        flow_version_id=FLOW_VERSION_ID,
        correlation_id=correlation_id,
        payload={"input": {"text": "billable"}},
    )
    node_run_id = await create_node_run(
        db_session,
        flow_run_id=flow_run_id,
        node_id=NODE_ID,
        correlation_id=correlation_id,
        status="RUNNING",
        canonical_status="RUNNING",
    )
    agent_run_1 = await create_agent_run(
        db_session,
        node_run_id=node_run_id,
        agent_version_id=AGENT_VERSION_ID,
        ai_execution_policy_version_id=POLICY_VERSION_ID,
        correlation_id=correlation_id,
        estimated_cost=0.5,
        status="COMPLETED",
        canonical_status="COMPLETED",
    )
    agent_run_2 = await create_agent_run(
        db_session,
        node_run_id=node_run_id,
        agent_version_id=AGENT_VERSION_ID,
        ai_execution_policy_version_id=POLICY_VERSION_ID,
        correlation_id=correlation_id,
        estimated_cost=1.0,
        status="COMPLETED",
        canonical_status="COMPLETED",
    )

    stmt = (
        sa.select(
            Session.tenant_id,
            AgentRun.agent_run_id,
            AgentRun.estimated_cost,
            AgentRun.billing_policy_version_id,
        )
        .select_from(AgentRun)
        .join(NodeRun, AgentRun.node_run_id == NodeRun.node_run_id)
        .join(FlowRun, NodeRun.flow_run_id == FlowRun.flow_run_id)
        .join(Session, FlowRun.session_id == Session.session_id)
        .where(Session.tenant_id == TENANT_ID)
        .where(AgentRun.agent_run_id.in_([agent_run_1, agent_run_2]))
        .where(AgentRun.billing_policy_version_id.is_not(None))
    )
    result = await db_session.execute(stmt)
    rows = result.all()
    totals: dict[str, float] = {}
    seen: set[str] = set()
    for row in rows:
        run_id = str(row.agent_run_id)
        if run_id in seen:
            continue
        seen.add(run_id)
        tenant = str(row.tenant_id)
        cost_value = row.estimated_cost
        cost = float(cost_value) if isinstance(cost_value, Decimal) else float(cost_value or 0)
        totals[tenant] = totals.get(tenant, 0.0) + cost

    assert totals[str(TENANT_ID)] == 1.5
    assert all(row.billing_policy_version_id is not None for row in rows)

    write_markdown(
        "cost-by-tenant-report.md",
        [
            text_block(
                "Billing summary",
                "Costs are summed per tenant using distinct agent_run_id values to avoid replay duplication.",
            ),
            json_block("Totals by tenant", totals),
            json_block(
                "Agent run rows",
                [
                    {
                        "tenant_id": str(row.tenant_id),
                        "agent_run_id": str(row.agent_run_id),
                        "billing_policy_version_id": str(row.billing_policy_version_id),
                        "estimated_cost": float(row.estimated_cost),
                    }
                    for row in rows
                ],
            ),
        ],
    )
