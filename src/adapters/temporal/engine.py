from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

import settings
from temporalio.client import (
    Client,
    WorkflowExecutionStatus,
    WorkflowFailureError,
    WorkflowHandle,
)
from temporalio.common import Priority, WorkflowIDReusePolicy
from temporalio.service import RPCError, RPCStatusCode

from adapters.temporal.client import build_temporal_client
from adapters.temporal.dtos import FlowRunWorkflowInput, FlowRunWorkflowResult, workflow_id_for
from adapters.temporal.workflow import FlowRunWorkflow
from domain.execution.ports.workflow_engine import WorkflowEnginePort
from domain.execution.schemas.workflow_dispatch import (
    FlowRunDispatch,
    FlowRunDispatchRequest,
    FlowRunDispatchStatus,
    FlowRunOutcome,
)
from exceptions.service_exceptions import DomainValidationException

_OUTCOME_BY_WORKFLOW_STATUS: dict[WorkflowExecutionStatus, FlowRunOutcome] = {
    WorkflowExecutionStatus.COMPLETED: FlowRunOutcome.COMPLETED,
    WorkflowExecutionStatus.FAILED: FlowRunOutcome.FAILED,
    WorkflowExecutionStatus.CANCELED: FlowRunOutcome.CANCELLED,
    WorkflowExecutionStatus.TERMINATED: FlowRunOutcome.CANCELLED,
    WorkflowExecutionStatus.TIMED_OUT: FlowRunOutcome.FAILED,
}


class TemporalWorkflowEngine(WorkflowEnginePort):
    def __init__(self) -> None:
        self._client: Client | None = None
        self._connect_lock = asyncio.Lock()

    async def client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._connect_lock:
            if self._client is None:
                self._client = await build_temporal_client()
        return self._client

    async def start_flow_run(self, *, request: FlowRunDispatchRequest) -> FlowRunDispatch:
        client = await self.client()
        workflow_id = workflow_id_for(str(request.flow_run_id), request.turn_index)
        run_timeout_ms = request.run_timeout_ms or settings.TEMPORAL_WORKFLOW_RUN_TIMEOUT_MS

        handle = await client.start_workflow(
            FlowRunWorkflow.run,
            FlowRunWorkflowInput(
                flow_run_id=str(request.flow_run_id),
                tenant_id=str(request.tenant_id),
                session_id=str(request.session_id),
                user_id=request.user_id,
                flow_id=str(request.flow_id),
                flow_version_id=str(request.flow_version_id),
                interaction_id=str(request.interaction_id),
                correlation_id=str(request.correlation_id),
                trace_id=str(request.trace_id) if request.trace_id else None,
                root_observation_id=request.root_observation_id,
                start_node_id=request.start_node_id,
                channel=request.channel,
                idempotency_key=request.idempotency_key,
                turn_index=request.turn_index,
            ),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            run_timeout=timedelta(milliseconds=run_timeout_ms),
            priority=self._priority(request.tenant_id),
        )

        return FlowRunDispatch(
            flow_run_id=request.flow_run_id,
            workflow_id=workflow_id,
            run_id=handle.first_execution_run_id or "",
        )

    async def start_resume_turn(self, *, request: FlowRunDispatchRequest) -> FlowRunDispatch:
        if request.turn_index <= 0:
            raise DomainValidationException(message="resume_turn_index_required")
        return await self.start_flow_run(request=request)

    async def await_flow_run_turn(
        self, *, dispatch: FlowRunDispatch, timeout_ms: int
    ) -> FlowRunDispatchStatus:
        client = await self.client()
        handle: WorkflowHandle = client.get_workflow_handle_for(
            FlowRunWorkflow.run,
            workflow_id=dispatch.workflow_id,
            run_id=dispatch.run_id or None,
        )
        try:
            result: FlowRunWorkflowResult = await asyncio.wait_for(
                handle.result(),
                timeout=timeout_ms / 1000,
            )
        except (asyncio.TimeoutError, WorkflowFailureError):
            return FlowRunDispatchStatus(
                flow_run_id=dispatch.flow_run_id,
                workflow_id=dispatch.workflow_id,
                run_id=dispatch.run_id,
            )
        return FlowRunDispatchStatus(
            flow_run_id=dispatch.flow_run_id,
            workflow_id=dispatch.workflow_id,
            run_id=dispatch.run_id,
            outcome=FlowRunOutcome(result.outcome),
            failure_reason=result.failure_reason,
            steps_executed=result.steps_executed,
        )

    async def cancel_flow_run(self, *, flow_run_id: UUID, reason: str) -> None:
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id_for(str(flow_run_id)))
        await handle.cancel()

    async def describe_flow_run(
        self, *, flow_run_id: UUID, workflow_id: str | None = None
    ) -> FlowRunDispatchStatus | None:
        client = await self.client()
        resolved_workflow_id = workflow_id or workflow_id_for(str(flow_run_id))
        handle = client.get_workflow_handle(resolved_workflow_id)
        try:
            description = await handle.describe()
        except RPCError as exc:
            if exc.status is RPCStatusCode.NOT_FOUND:
                return None
            raise
        return FlowRunDispatchStatus(
            flow_run_id=flow_run_id,
            workflow_id=resolved_workflow_id,
            run_id=description.run_id,
            outcome=_OUTCOME_BY_WORKFLOW_STATUS.get(description.status),
        )

    @staticmethod
    def _priority(tenant_id: UUID) -> Priority | None:
        if not settings.TEMPORAL_FAIRNESS_ENABLED:
            return None
        return Priority(fairness_key=str(tenant_id))
