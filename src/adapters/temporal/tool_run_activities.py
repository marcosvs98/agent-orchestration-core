from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from adapters.temporal.tool_run_dtos import ScheduledToolRunInput, ScheduledToolRunResult
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from exceptions.service_exceptions import BaseServiceException, format_exception


class ScheduledToolRunActivities:
    """Executes a previously created tool run when its schedule fires."""

    def __init__(
        self,
        tool_orchestrator: ToolOrchestrator,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.tool_orchestrator = tool_orchestrator
        self.tracer = tracer

    @activity.defn
    async def execute_scheduled_tool_run(
        self, payload: ScheduledToolRunInput
    ) -> ScheduledToolRunResult:
        tool_run_id = UUID(payload.tool_run_id)
        with self.tracer.observe(
            as_type="tool",
            name="adapters.temporal.scheduled_tool_run.execute",
            input={"tool_run_id": payload.tool_run_id, "run_at": payload.run_at.isoformat()},
        ) as span:
            try:
                output = await self.tool_orchestrator.execute_tool_run(tool_run_id=tool_run_id)
            except BaseServiceException as exc:
                raise ApplicationError(
                    exc.message,
                    type=type(exc).__name__,
                    non_retryable=True,
                ) from exc
            except Exception as exc:
                raise ApplicationError(
                    format_exception(exc),
                    type=type(exc).__name__,
                ) from exc
            result = ScheduledToolRunResult(
                tool_run_id=payload.tool_run_id,
                succeeded=True,
                output=output if isinstance(output, dict) else {"result": output},
            )
            if span:
                span.update(output=result.model_dump(mode="json"))
            return result
