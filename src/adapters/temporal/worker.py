from __future__ import annotations

import asyncio
from datetime import timedelta

import settings
from temporalio.worker import Worker

from adapters.observability.logging import configure_logger, get_logger
from adapters.observability.otel_bootstrap import bootstrap_telemetry
from adapters.temporal.activities import FlowRunActivities
from adapters.temporal.client import build_temporal_client
from adapters.temporal.sandbox import build_workflow_runner
from adapters.temporal.tool_run_activities import ScheduledToolRunActivities
from adapters.temporal.tool_run_workflow import ScheduledToolRunWorkflow
from adapters.temporal.workflow import FlowRunWorkflow
from containers import ApplicationContainer
from domain.execution.services.flow_run_reconciler import FlowRunReconciler

logger = get_logger(__name__)


async def main() -> None:
    configure_logger(is_async=False)
    bootstrap_telemetry(component="temporal-worker")

    container = ApplicationContainer()
    container.config.from_dict({"application_name": settings.APPLICATION_NAME})
    container.init_resources()

    execution_service = container.execution.execution_service()
    tracer = container.adapters.tracer()
    activities = FlowRunActivities(execution_service=execution_service, tracer=tracer)
    tool_run_activities = ScheduledToolRunActivities(
        tool_orchestrator=container.execution.tool_orchestrator(),
        tracer=tracer,
    )

    client = await build_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflow_runner=build_workflow_runner(),
        workflows=[FlowRunWorkflow],
        activities=[
            activities.prepare_flow_run,
            activities.execute_node,
            activities.finalize_flow_run,
        ],
        max_concurrent_activities=settings.TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES,
        max_concurrent_workflow_tasks=settings.TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS,
        graceful_shutdown_timeout=timedelta(seconds=30),
    )

    tool_run_worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TOOL_RUN_TASK_QUEUE,
        workflow_runner=build_workflow_runner(),
        workflows=[ScheduledToolRunWorkflow],
        activities=[tool_run_activities.execute_scheduled_tool_run],
        max_concurrent_activities=settings.TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES,
        max_concurrent_workflow_tasks=settings.TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS,
        graceful_shutdown_timeout=timedelta(seconds=30),
    )

    runnables = [worker.run(), tool_run_worker.run()]

    if settings.FLOW_RUN_RECONCILER_ENABLED:
        reconciler = FlowRunReconciler(
            repository=execution_service.repository,
            workflow_engine=execution_service.workflow_engine,
            stale_after_seconds=settings.FLOW_RUN_RECONCILER_STALE_AFTER_SECONDS,
            batch_size=settings.FLOW_RUN_RECONCILER_BATCH_SIZE,
        )
        runnables.append(
            reconciler.run_forever(interval_seconds=settings.FLOW_RUN_RECONCILER_INTERVAL_SECONDS)
        )

    logger.info(
        "temporal_worker_started",
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        tool_run_task_queue=settings.TEMPORAL_TOOL_RUN_TASK_QUEUE,
        namespace=settings.TEMPORAL_NAMESPACE,
        host=settings.TEMPORAL_HOST,
        reconciler_enabled=settings.FLOW_RUN_RECONCILER_ENABLED,
    )
    try:
        await asyncio.gather(*runnables)
    finally:
        tracer.shutdown()
        container.shutdown_resources()


if __name__ == "__main__":
    asyncio.run(main())
