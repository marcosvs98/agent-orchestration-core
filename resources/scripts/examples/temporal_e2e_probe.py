"""End-to-end probe: dispatch a real flow run through Temporal and a live worker.

Inserts the minimum fixture rows, starts FlowRunWorkflow via the real
TemporalWorkflowEngine, and reports the resulting flow_run row. The graph uses
an unknown node type so the run reaches a terminal state without any LLM call,
which keeps the probe free of provider credentials while still exercising the
whole chain: engine -> Temporal -> worker -> activities -> repository.

Usage:
    PYTHONPATH=src TEMPORAL_ENABLED=true uv run python \\
        resources/scripts/examples/temporal_e2e_probe.py
"""

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import asyncpg

import settings
from adapters.temporal.engine import TemporalWorkflowEngine
from domain.execution.schemas.workflow_dispatch import FlowRunDispatchRequest
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator

DSN = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def seed(conn: asyncpg.Connection) -> dict[str, object]:
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()
    snapshot_id = uuid4()
    session_id = uuid4()
    interaction_id = uuid4()
    flow_run_id = uuid4()
    correlation_id = uuid4()
    node_id = uuid4()
    terminal_node_id = uuid4()

    graph = {
        "start_node": str(node_id),
        "nodes": {
            str(node_id): {"type": "TotallyUnknownNodeType", "config": None},
            str(terminal_node_id): {"type": "ResponseBuilder", "config": None},
        },
        "edges": [
            {
                "from_node": str(node_id),
                "to_node": str(terminal_node_id),
                "condition": "1 == 1",
                "compiled_condition": EdgeEvaluator.compile_condition("1 == 1"),
            }
        ],
    }

    await conn.execute(
        "INSERT INTO tenant (tenant_id, name, is_active) VALUES ($1, $2, true)",
        tenant_id,
        "temporal-probe",
    )
    await conn.execute(
        "INSERT INTO flow (flow_id, tenant_id, name) VALUES ($1, $2, $3)",
        flow_id,
        tenant_id,
        "probe-flow",
    )
    await conn.execute(
        """INSERT INTO flow_version
           (flow_version_id, flow_id, status, version_major, version_minor,
            version_patch, is_active)
           VALUES ($1, $2, 'PUBLISHED', 1, 0, 0, true)""",
        flow_version_id,
        flow_id,
    )
    await conn.execute(
        """INSERT INTO flow_graph_snapshot
           (flow_graph_snapshot_id, flow_version_id, graph_hash, snapshot,
            compiled_by)
           VALUES ($1, $2, $3, $4, 'temporal-probe')""",
        snapshot_id,
        flow_version_id,
        f"probe-{snapshot_id}",
        json.dumps(graph),
    )
    await conn.execute(
        "INSERT INTO end_user (end_user_id, tenant_id, user_id) VALUES ($1, $2, $3)",
        uuid4(),
        tenant_id,
        "probe-user",
    )
    await conn.execute(
        "INSERT INTO session (session_id, tenant_id, user_id) VALUES ($1, $2, $3)",
        session_id,
        tenant_id,
        "probe-user",
    )
    await conn.execute(
        """INSERT INTO interaction
           (interaction_id, session_id, channel, payload, output, headers,
            interaction_metadata)
           VALUES ($1, $2, 'http', '{}', '{}', '{}', '{}')""",
        interaction_id,
        session_id,
    )
    await conn.execute(
        """INSERT INTO flow_run
           (flow_run_id, flow_version_id, session_id, user_id, interaction_id,
            status, canonical_status, correlation_id, input, output, error,
            flow_graph_snapshot_id, runtime_contract)
           VALUES ($1, $2, $3, $4, $5, 'CREATED', 'CREATED', $6,
                   $7, '{}', '{}', $8, '{}')""",
        flow_run_id,
        flow_version_id,
        session_id,
        "probe-user",
        interaction_id,
        correlation_id,
        json.dumps({"user_input": "probe"}),
        snapshot_id,
    )

    return {
        "tenant_id": tenant_id,
        "flow_id": flow_id,
        "flow_version_id": flow_version_id,
        "session_id": session_id,
        "interaction_id": interaction_id,
        "flow_run_id": flow_run_id,
        "correlation_id": correlation_id,
    }


async def main() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        ids = await seed(conn)
        print(f"seeded flow_run {ids['flow_run_id']}")

        engine = TemporalWorkflowEngine()
        dispatch = await engine.start_flow_run(
            request=FlowRunDispatchRequest(
                flow_run_id=ids["flow_run_id"],
                tenant_id=ids["tenant_id"],
                session_id=ids["session_id"],
                user_id="probe-user",
                flow_id=ids["flow_id"],
                flow_version_id=ids["flow_version_id"],
                interaction_id=ids["interaction_id"],
                correlation_id=ids["correlation_id"],
            )
        )
        print(f"dispatched workflow_id={dispatch.workflow_id} run_id={dispatch.run_id}")

        await conn.execute(
            """UPDATE flow_run
               SET temporal_workflow_id = $2, temporal_run_id = $3,
                   status = 'QUEUED', canonical_status = 'CREATED'
               WHERE flow_run_id = $1""",
            ids["flow_run_id"],
            dispatch.workflow_id,
            dispatch.run_id,
        )

        wait_ms = int(os.getenv("PROBE_WAIT_MS", "60000"))
        status = await engine.await_flow_run_turn(dispatch=dispatch, timeout_ms=wait_ms)
        print(f"workflow outcome={status.outcome} reason={status.failure_reason}")

        row = await conn.fetchrow(
            """SELECT status, canonical_status, error, temporal_workflow_id,
                      temporal_run_id
               FROM flow_run WHERE flow_run_id = $1""",
            ids["flow_run_id"],
        )
        print(f"flow_run.status            = {row['status']}")
        print(f"flow_run.canonical_status  = {row['canonical_status']}")
        print(f"flow_run.temporal_workflow_id = {row['temporal_workflow_id']}")
        print(f"flow_run.temporal_run_id      = {row['temporal_run_id']}")
        print(f"flow_run.error             = {row['error']}")

        events = await conn.fetch(
            """SELECT type, event_sequence FROM execution_event
               WHERE flow_run_id = $1 ORDER BY event_sequence""",
            ids["flow_run_id"],
        )
        print(f"execution_events           = {[e['type'] for e in events]}")

        graph_state = await conn.fetchrow(
            "SELECT state FROM graph_state WHERE flow_run_id = $1",
            ids["flow_run_id"],
        )
        print(f"graph_state seeded         = {graph_state is not None}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
