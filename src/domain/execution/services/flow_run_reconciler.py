from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from adapters.observability.logging import get_logger
from domain.execution.ports.workflow_engine import WorkflowEnginePort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.schemas.workflow_dispatch import FlowRunOutcome

logger = get_logger(__name__)

RECONCILED_FAILURE_MESSAGE = "flow_run_abandoned"


class FlowRunReconciler:
    """Fails flow runs that are stranded between dispatch and finalization.

    A crash after ``prepare_flow_run`` and before ``finalize_flow_run`` leaves the row
    QUEUED or RUNNING forever: the workflow is gone and nothing else writes a terminal
    state. This sweeps rows whose ``updated_at`` has not moved within the stale window
    and asks the engine whether their workflow is still alive before failing them.
    """

    def __init__(
        self,
        *,
        repository: ExecutionRepository,
        workflow_engine: WorkflowEnginePort | None,
        stale_after_seconds: int,
        batch_size: int,
    ) -> None:
        self.repository = repository
        self.workflow_engine = workflow_engine
        self.stale_after_seconds = stale_after_seconds
        self.batch_size = batch_size

    async def run_forever(self, *, interval_seconds: int) -> None:
        while True:
            try:
                reconciled = await self.reconcile_once()
                if reconciled:
                    logger.warning("flow_run_reconciler_failed_runs", count=reconciled)
            except Exception:
                logger.exception("flow_run_reconciler_pass_failed")
            await asyncio.sleep(interval_seconds)

    async def reconcile_once(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.stale_after_seconds)
        stale = await self.repository.list_stale_running_flow_runs(
            older_than=cutoff, limit=self.batch_size
        )
        reconciled = 0
        for flow_run in stale:
            if await self._is_still_running(flow_run):
                continue
            await self._fail(flow_run)
            reconciled += 1
        return reconciled

    async def _is_still_running(self, flow_run) -> bool:
        if self.workflow_engine is None:
            return False
        try:
            status = await self.workflow_engine.describe_flow_run(
                flow_run_id=flow_run.flow_run_id,
                workflow_id=flow_run.temporal_workflow_id,
            )
        except Exception:
            logger.exception(
                "flow_run_reconciler_describe_failed",
                flow_run_id=str(flow_run.flow_run_id),
            )
            return True
        if status is None:
            return False
        return status.outcome is None or status.outcome is FlowRunOutcome.WAITING

    async def _fail(self, flow_run) -> None:
        flow_run_id: UUID = flow_run.flow_run_id
        await self.repository.fail_flow_run(
            flow_run_id=flow_run_id,
            failure_reason=FlowFailureReason.STRUCTURAL_ERROR,
            error={
                "reason": FlowFailureReason.STRUCTURAL_ERROR.value,
                "message": RECONCILED_FAILURE_MESSAGE,
                "stale_after_seconds": self.stale_after_seconds,
            },
        )
        session_id, tenant_id = await self.repository.get_flow_context(flow_run_id)
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.FlowFailed,
            payload={
                "reason": FlowFailureReason.STRUCTURAL_ERROR.value,
                "message": RECONCILED_FAILURE_MESSAGE,
            },
            correlation_id=flow_run.correlation_id,
            causation_id=None,
            schema_version=1,
        )
        logger.warning(
            "flow_run_reconciled_to_failed",
            flow_run_id=str(flow_run_id),
            previous_status=str(flow_run.status),
        )
