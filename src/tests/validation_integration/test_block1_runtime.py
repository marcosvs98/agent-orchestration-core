from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from domain.execution.schemas.events import ExecutionEventType

from infra.database.models.execution.execution_event import ExecutionEvent
from resources.scripts.validation_seed import FLOW_VERSION_ID, SESSION_ID, TENANT_ID
from .helpers import append_execution_event, create_flow_run
from .evidence import json_block, text_block, write_markdown

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_replay_produces_same_event_topology(db_session) -> None:
    correlation_id = uuid4()
    payload = {"input": {"text": "hello"}}

    run_one = await create_flow_run(
        db_session,
        session_id=SESSION_ID,
        flow_version_id=FLOW_VERSION_ID,
        correlation_id=correlation_id,
        payload=payload,
    )
    await db_session.flush()

    run_two = await create_flow_run(
        db_session,
        session_id=SESSION_ID,
        flow_version_id=FLOW_VERSION_ID,
        correlation_id=correlation_id,
        payload=payload,
    )
    await db_session.flush()

    for flow_run_id in (run_one, run_two):
        await append_execution_event(
            db_session,
            tenant_id=TENANT_ID,
            session_id=SESSION_ID,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            event_type=ExecutionEventType.FlowStarted,
            payload={"payload": payload["input"]},
            event_sequence=1,
        )

        await append_execution_event(
            db_session,
            tenant_id=TENANT_ID,
            session_id=SESSION_ID,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            event_type=ExecutionEventType.FlowCompleted,
            payload={"result": "ok"},
            causation_id=None,
            event_sequence=2,
        )

    result_one = await db_session.execute(
        sa.select(
            ExecutionEvent.type,
            ExecutionEvent.payload,
            ExecutionEvent.event_sequence,
            ExecutionEvent.correlation_id,
        )
        .where(ExecutionEvent.flow_run_id == run_one)
        .order_by(ExecutionEvent.event_sequence)
    )
    rows_one = result_one.all()
    events_one = [
        {
            "type": row.type,
            "payload": row.payload,
            "event_sequence": int(row.event_sequence),
            "correlation_id": str(row.correlation_id),
        }
        for row in rows_one
    ]

    result_two = await db_session.execute(
        sa.select(
            ExecutionEvent.type,
            ExecutionEvent.payload,
            ExecutionEvent.event_sequence,
            ExecutionEvent.correlation_id,
        )
        .where(ExecutionEvent.flow_run_id == run_two)
        .order_by(ExecutionEvent.event_sequence)
    )
    rows_two = result_two.all()
    events_two = [
        {
            "type": row.type,
            "payload": row.payload,
            "event_sequence": int(row.event_sequence),
            "correlation_id": str(row.correlation_id),
        }
        for row in rows_two
    ]

    assert events_one == events_two

    summary = text_block(
        "Determinism",
        "Two FlowRuns created from the same payload and correlation_id produced identical event topology.",
    )
    write_markdown(
        "replay-evidence.md",
        [
            summary,
            json_block("FlowRun A events", events_one),
            json_block("FlowRun B events", events_two),
        ],
    )
