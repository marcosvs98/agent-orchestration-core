from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.execution.schemas.workflow_dispatch import (
    FlowRunDispatch,
    FlowRunDispatchRequest,
    FlowRunDispatchStatus,
)


class WorkflowEnginePort(Protocol):
    """Durable execution engine for flow runs.

    Implementations own where a flow run actually executes. Starting a run is
    decoupled from awaiting it so the HTTP boundary can answer either
    asynchronously or synchronously from the same dispatch.

    Execution is turn-scoped: a workflow returns when the run reaches COMPLETED,
    FAILED or WAITING. Resuming a WAITING run therefore starts a new workflow for
    the next turn rather than signalling the previous one, which has already
    returned. Graph state lives in Postgres, so the new turn resumes from
    ``start_node_id`` over the state the previous turn left behind.
    """

    async def start_flow_run(self, *, request: FlowRunDispatchRequest) -> FlowRunDispatch: ...

    async def await_flow_run_turn(
        self, *, dispatch: FlowRunDispatch, timeout_ms: int
    ) -> FlowRunDispatchStatus: ...

    async def start_resume_turn(self, *, request: FlowRunDispatchRequest) -> FlowRunDispatch: ...

    async def cancel_flow_run(self, *, flow_run_id: UUID, reason: str) -> None: ...

    async def describe_flow_run(
        self, *, flow_run_id: UUID, workflow_id: str | None = None
    ) -> FlowRunDispatchStatus | None: ...
