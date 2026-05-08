from __future__ import annotations

import asyncio
from typing import Any

from domain.conversation.schemas.conversation import ConversationEvent, SSEEventType
from domain.execution.services.observability.hooks import ExecutionEventHook


class StreamBridge(ExecutionEventHook):
    def __init__(self, queue: asyncio.Queue[ConversationEvent | None]) -> None:
        self._queue = queue

    async def _push(self, event_type: SSEEventType, payload: dict[str, Any] | None = None) -> None:
        await self._queue.put(ConversationEvent(event_type=event_type, payload=payload or {}))

    async def _done(self) -> None:
        await self._queue.put(None)

    async def push_content_delta(self, delta: str, node_id: str | None = None) -> None:
        await self._push(
            SSEEventType.CONTENT_DELTA,
            {"delta": delta, "node_id": node_id},
        )

    async def on_flow_start(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.TOOL_PROGRESS,
            {
                "phase": "flow_started",
                "payload": kwargs.get("payload") or {},
            },
        )

    async def on_node_start(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.TOOL_PROGRESS,
            {
                "phase": "node_started",
                "payload": kwargs.get("payload") or {},
            },
        )

    async def on_node_complete(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.TOOL_PROGRESS,
            {
                "phase": "node_completed",
                "payload": kwargs.get("payload") or {},
            },
        )

    async def on_edge_evaluated(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.TOOL_PROGRESS,
            {
                "phase": "edge_evaluated",
                "payload": kwargs.get("payload") or {},
            },
        )

    async def on_flow_complete(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.DONE,
            {
                "flow_run_id": str(kwargs.get("flow_run_id")),
            },
        )
        await self._done()

    async def on_flow_failed(self, **kwargs: Any) -> None:
        await self._push(
            SSEEventType.ERROR,
            {
                "flow_run_id": str(kwargs.get("flow_run_id")),
                "payload": kwargs.get("payload") or {},
            },
        )
        await self._done()
