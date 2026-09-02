from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa

from domain.execution.schemas.events import ExecutionEventType
from infra.database.models.conversation.interaction import Interaction
from infra.database.models.execution.execution_event import ExecutionEvent
from resources.scripts.validation_seed import FLOW_VERSION_ID, SESSION_ID, TENANT_ID
from .helpers import append_execution_event, create_flow_run

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_channel_agnostic_topology(db_session) -> None:
    payload = {"text": "normalize-me"}
    correlation_id = uuid4()
    flows = {}
    for channel in ("http", "whatsapp"):
        interaction = Interaction(
            session_id=SESSION_ID,
            channel=channel,
            payload=payload,
            output={},
            headers={},
            interaction_metadata={},
            result_node_run_id=None,
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )
        db_session.add(interaction)
        await db_session.commit()
        flow_run_id = await create_flow_run(
            db_session,
            session_id=SESSION_ID,
            flow_version_id=FLOW_VERSION_ID,
            correlation_id=correlation_id,
            payload={"channel": channel, "input": payload},
        )
        await append_execution_event(
            db_session,
            tenant_id=TENANT_ID,
            session_id=SESSION_ID,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            event_type=ExecutionEventType.FlowStarted,
            payload={"channel": channel, "interaction_id": str(interaction.interaction_id)},
        )
        await append_execution_event(
            db_session,
            tenant_id=TENANT_ID,
            session_id=SESSION_ID,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            event_type=ExecutionEventType.FlowCompleted,
            payload={"channel": channel},
        )
        flows[channel] = flow_run_id

    async def fetch(flow_run_id):
        result = await db_session.execute(
            sa.select(
                ExecutionEvent.type,
                ExecutionEvent.payload,
                ExecutionEvent.event_sequence,
            )
            .where(ExecutionEvent.flow_run_id == flow_run_id)
            .order_by(ExecutionEvent.event_sequence)
        )
        rows = result.all()
        return [
            {
                "type": row.type,
                "event_sequence": int(row.event_sequence),
                "payload": row.payload,
            }
            for row in rows
        ]

    http_events = await fetch(flows["http"])
    whatsapp_events = await fetch(flows["whatsapp"])
    normalized_http = [
        {
            "type": e["type"],
            "event_sequence": e["event_sequence"],
            "payload_keys": sorted(e["payload"].keys()),
        }
        for e in http_events
    ]
    normalized_whatsapp = [
        {
            "type": e["type"],
            "event_sequence": e["event_sequence"],
            "payload_keys": sorted(e["payload"].keys()),
        }
        for e in whatsapp_events
    ]
    assert normalized_http == normalized_whatsapp
