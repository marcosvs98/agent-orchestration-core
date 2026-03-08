from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from fastapi.sse import ServerSentEvent

from domain.conversation.ports.service import ConversationServicePort
from domain.conversation.schemas.conversation import (
    ConversationEvent,
    ConversationRequest,
    SSEEventType,
)
from domain.conversation.services.sse_writer import SSEWriter
from domain.conversation.services.stream_bridge import StreamBridge
from domain.execution.schemas.execution import Channel, FlowRunCreate, FlowRunInput
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.observability.hooks import (
    CompositeHook,
    ExecutionEventHook,
)


class ConversationService(ConversationServicePort):
    def __init__(self, execution_service: ExecutionService) -> None:
        self.execution_service = execution_service
        self._hook_lock = asyncio.Lock()

    async def _run_flow(
        self,
        *,
        tenant_id: UUID,
        request: ConversationRequest,
        queue: asyncio.Queue[ConversationEvent | None],
        channel: Channel,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> None:
        stream_bridge = StreamBridge(queue)

        async def _on_content_delta(delta: str) -> None:
            await stream_bridge.push_content_delta(delta)

        flow_run = FlowRunCreate(
            flow_id=request.flow_id,
            flow_version_id=request.flow_version_id,
            session_id=request.session_id or uuid4(),
            user_id=request.user_id,
            correlation_id=request.correlation_id,
            input=FlowRunInput(user_input=request.user_input),
            metadata=request.metadata,
        )
        endpoint = "/core/v1/conversations"
        idempotency_key = request_id or str(uuid4())

        async with self._hook_lock:
            original_hook: ExecutionEventHook = self.execution_service.hook
            original_runtime_hook: ExecutionEventHook | None = (
                self.execution_service.runtime.hook
            )
            composite_hook = CompositeHook([original_hook, stream_bridge])
            self.execution_service.hook = composite_hook
            self.execution_service.runtime.hook = composite_hook
            try:
                response = await self.execution_service.create_flow_run(
                    tenant_id=tenant_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    flow_run=flow_run,
                    channel=channel,
                    headers=headers,
                    external_message_id=external_message_id,
                    request_id=request_id,
                    trace_id=trace_id,
                    on_content_delta=_on_content_delta,
                )
                await self.execution_service.repository.create_response_artifact_for_flow_run(
                    flow_run_id=response.id,
                    payload=response.output,
                )
            except Exception as exc:
                await queue.put(
                    ConversationEvent(
                        event_type=SSEEventType.ERROR,
                        payload={"message": str(exc)},
                    )
                )
                await queue.put(None)
            finally:
                self.execution_service.hook = original_hook
                self.execution_service.runtime.hook = original_runtime_hook

    async def execute_turn(
        self,
        *,
        tenant_id: UUID,
        request: ConversationRequest,
        channel: Channel,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
        last_event_id: int | None,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue(maxsize=64)
        writer = SSEWriter(
            queue=queue,
            start_event_id=last_event_id if last_event_id is not None else 0,
        )
        task = asyncio.create_task(
            self._run_flow(
                tenant_id=tenant_id,
                request=request,
                queue=queue,
                channel=channel,
                headers=headers,
                external_message_id=external_message_id,
                request_id=request_id,
                trace_id=trace_id,
            )
        )

        async def _generator() -> AsyncGenerator[ServerSentEvent, None]:
            try:
                async for chunk in writer.stream():
                    yield chunk
            finally:
                if not task.done():
                    task.cancel()
                try:
                    await task
                except Exception:
                    pass

        return _generator()
