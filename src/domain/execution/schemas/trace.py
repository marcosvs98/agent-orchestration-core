from uuid import UUID

from pydantic import BaseModel


class TraceContext(BaseModel):
    trace_id: UUID
    flow_run_id: UUID
    tenant_id: UUID
    root_observation_id: str | None = None
    flow_name: str | None = None
