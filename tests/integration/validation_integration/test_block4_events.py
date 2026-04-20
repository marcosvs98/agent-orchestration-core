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


async def test_events_enable_audit_trail(db_session) -> None:
    correlation_id = uuid4()
    flow_run_id = await create_flow_run(
        db_session,
        session_id=SESSION_ID,
        flow_version_id=FLOW_VERSION_ID,
        correlation_id=correlation_id,
        payload={"input": {"text": "audit"}},
    )
    await db_session.flush()

    started_event_id = await append_execution_event(
        db_session,
        tenant_id=TENANT_ID,
        session_id=SESSION_ID,
        flow_run_id=flow_run_id,
        correlation_id=correlation_id,
        event_type=ExecutionEventType.FlowStarted,
        payload={"channel": "http"},
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
        causation_id=started_event_id,
        event_sequence=2,
    )

    result = await db_session.execute(
        sa.select(
            ExecutionEvent.type,
            ExecutionEvent.payload,
            ExecutionEvent.event_sequence,
            ExecutionEvent.correlation_id,
            ExecutionEvent.causation_id,
        )
        .where(ExecutionEvent.flow_run_id == flow_run_id)
        .order_by(ExecutionEvent.event_sequence)
    )
    rows = result.all()
    events = [
        {
            "type": row.type,
            "event_sequence": int(row.event_sequence),
            "correlation_id": str(row.correlation_id),
            "causation_id": str(row.causation_id) if row.causation_id else None,
            "payload": row.payload,
        }
        for row in rows
    ]

    write_markdown(
        "event-taxonomy-final.md",
        [
            text_block(
                "Data-first audit trail",
                "Events carry correlation_id, causation_id, schema_version, and payload; audit answers rely on persisted data (channel metadata included) instead of logs.",
            ),
            json_block("Event sample", events),
        ],
    )
