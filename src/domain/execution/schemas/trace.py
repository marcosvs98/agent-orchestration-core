from uuid import UUID

from pydantic import BaseModel


class TraceContext(BaseModel):
    trace_id: UUID
    flow_run_id: UUID
    tenant_id: UUID
    session_id: UUID | None = None
    user_id: str | None = None
    root_observation_id: str | None = None
    flow_name: str | None = None
    flow_id: UUID | None = None
    flow_version_id: UUID | None = None
    interaction_id: UUID | None = None
    correlation_id: UUID | None = None
    channel: str | None = None
    external_message_id: str | None = None
    graph_snapshot_id: UUID | None = None
    execution_plan_hash: str | None = None
