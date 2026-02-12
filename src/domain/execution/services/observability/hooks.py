from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID

from domain.context.schemas.memory_write import MemoryWriteEventContext
from domain.context.services.memory_extraction_processor import MemoryExtractionProcessor
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType

logger = logging.getLogger(__name__)


class ExecutionEventHook(ABC):
    @abstractmethod
    async def on_flow_start(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    async def on_node_start(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    async def on_node_complete(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    async def on_edge_evaluated(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    async def on_flow_complete(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    async def on_flow_failed(self, **kwargs: Any) -> None:
        pass


class DbExecutionEventHook(ExecutionEventHook):
    """Execution event hook that persists events to DB; public methods use tracer."""

    def __init__(
        self, repository: ExecutionRepository, tracer: RuntimeTracerPort
    ) -> None:
        self.repository = repository
        self.tracer = tracer

    async def _safe_emit(
        self, *, event_type: ExecutionEventType, data: Dict[str, Any]
    ) -> None:
        try:
            await self.repository.append_execution_event(
                **data, event_type=event_type.value
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to append execution event (swallowed): %s", exc)

    async def on_flow_start(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.FlowStarted.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.FlowStarted.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.FlowStarted,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": None,
                    "edge_id": None,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})

    async def on_node_start(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.NodeStarted.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.NodeStarted.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.NodeStarted,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": node_id,
                    "edge_id": None,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})

    async def on_node_complete(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.NodeCompleted.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.NodeCompleted.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.NodeCompleted,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": node_id,
                    "edge_id": None,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})

    async def on_edge_evaluated(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        edge_id: str | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.EdgeEvaluated.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.EdgeEvaluated.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.EdgeEvaluated,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": node_id,
                    "edge_id": edge_id,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})

    async def on_flow_complete(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.FlowCompleted.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.FlowCompleted.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.FlowCompleted,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": None,
                    "edge_id": None,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})

    async def on_flow_failed(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        with self.tracer.observe(
            as_type="event",
            name=f"event.{ExecutionEventType.FlowFailed.value}",
            input=payload,
            metadata={"event_type": ExecutionEventType.FlowFailed.value},
        ) as event_handle:
            await self._safe_emit(
                event_type=ExecutionEventType.FlowFailed,
                data={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "flow_run_id": flow_run_id,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": None,
                    "edge_id": None,
                },
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})


class MemoryExtractionHook(ExecutionEventHook):
    def __init__(
        self,
        base_hook: ExecutionEventHook,
        memory_extraction_processor: MemoryExtractionProcessor,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.base_hook = base_hook
        self.memory_extraction_processor = memory_extraction_processor
        self.tracer = tracer

    async def on_flow_start(self, **kwargs: Any) -> None:
        await self.base_hook.on_flow_start(**kwargs)

    async def on_node_start(self, **kwargs: Any) -> None:
        await self.base_hook.on_node_start(**kwargs)

    async def on_node_complete(self, **kwargs: Any) -> None:
        await self.base_hook.on_node_complete(**kwargs)

    async def on_edge_evaluated(self, **kwargs: Any) -> None:
        await self.base_hook.on_edge_evaluated(**kwargs)

    async def on_flow_complete(self, **kwargs: Any) -> None:
        await self.base_hook.on_flow_complete(**kwargs)
        tenant_id = kwargs.get("tenant_id")
        user_id = kwargs.get("user_id")
        session_id = kwargs.get("session_id")
        flow_run_id = kwargs.get("flow_run_id")
        correlation_id = kwargs.get("correlation_id")
        payload = kwargs.get("payload")
        causation_id = kwargs.get("causation_id")
        if (
            not isinstance(tenant_id, UUID)
            or not isinstance(user_id, str)
            or not isinstance(session_id, UUID)
            or not isinstance(flow_run_id, UUID)
            or not isinstance(correlation_id, UUID)
            or not isinstance(payload, dict)
        ):
            return
        flow_output = payload.get("payload")
        if not isinstance(flow_output, dict):
            flow_output = {}
        config_payload = payload.get("memory_extraction_config")
        if not isinstance(config_payload, dict):
            return
        with self.tracer.observe(
            as_type="span",
            name="domain.context.memory_extraction.hook",
            input={
                "flow_run_id": str(flow_run_id),
                "flow_output_keys": sorted(str(key) for key in flow_output.keys()),
            },
        ):
            try:
                await self.memory_extraction_processor.execute(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    flow_output=flow_output,
                    config_payload=config_payload,
                    event_context=MemoryWriteEventContext(
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        causation_id=causation_id
                        if isinstance(causation_id, UUID)
                        else None,
                    ),
                    trace_id=correlation_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Post-flow memory extraction failed (swallowed): %s",
                    exc,
                )

    async def on_flow_failed(self, **kwargs: Any) -> None:
        await self.base_hook.on_flow_failed(**kwargs)
