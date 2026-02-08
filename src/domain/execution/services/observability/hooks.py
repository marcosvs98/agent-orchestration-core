from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.ports.runtime_tracer import RuntimeTracerPort

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
    def __init__(
        self, repository: ExecutionRepository, tracer: RuntimeTracerPort
    ) -> None:
        self.repository = repository
        self.tracer = tracer

    async def _safe_emit(
        self, *, event_type: ExecutionEventType, data: Dict[str, Any]
    ) -> None:
        try:
            
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.hooks.append_execution_event",
                input={"event_type": event_type.value},
            ):
                await self.repository.append_execution_event(
                    **data, event_type=event_type.value
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to append execution event (swallowed): %s", exc)

    async def on_flow_start(
        self,
        *,
        tenant_id: UUID,
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
        ) as handle:
            handle.success(output={"status": "recorded"})
        await self._safe_emit(
            event_type=ExecutionEventType.FlowStarted,
            data={
                "tenant_id": tenant_id,
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

    async def on_node_start(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        await self._safe_emit(
            event_type=ExecutionEventType.NodeStarted,
            data={
                "tenant_id": tenant_id,
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

    async def on_node_complete(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        await self._safe_emit(
            event_type=ExecutionEventType.NodeCompleted,
            data={
                "tenant_id": tenant_id,
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

    async def on_edge_evaluated(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None,
        edge_id: str | None,
        payload: dict[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
    ) -> None:
        await self._safe_emit(
            event_type=ExecutionEventType.EdgeEvaluated,
            data={
                "tenant_id": tenant_id,
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

    async def on_flow_complete(
        self,
        *,
        tenant_id: UUID,
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
        ) as handle:
            handle.success(output={"status": "recorded"})
        await self._safe_emit(
            event_type=ExecutionEventType.FlowCompleted,
            data={
                "tenant_id": tenant_id,
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

    async def on_flow_failed(
        self,
        *,
        tenant_id: UUID,
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
        ) as handle:
            handle.success(output={"status": "recorded"})
        await self._safe_emit(
            event_type=ExecutionEventType.FlowFailed,
            data={
                "tenant_id": tenant_id,
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
