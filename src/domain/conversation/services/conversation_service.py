from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from fastapi.sse import ServerSentEvent

import settings
from adapters.mcp.conversation_mcp_context import get_conversation_mcp_config
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.conversation.ports.service import ConversationServicePort
from domain.conversation.schemas.conversation import (
    ConversationEvent,
    ConversationRequest,
    SSEEventType,
)
from domain.conversation.services.sse_writer import SSEWriter
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import Channel
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.user_prompts.repositories.user_prompts_repository import (
    UserPromptsRepository,
)
from exceptions.service_exceptions import DomainValidationException


class ConversationService(ConversationServicePort):
    def __init__(
        self,
        openai_provider: OpenAIProviderAdapter,
        idempotency: IdempotencyService,
        execution_repository: ExecutionRepository,
        agents_repository: AgentsRepository,
        user_prompts_repository: UserPromptsRepository,
    ) -> None:
        self.openai_provider = openai_provider
        self.idempotency = idempotency
        self.execution_repository = execution_repository
        self.agents_repository = agents_repository
        self.user_prompts_repository = user_prompts_repository

    async def _resolve_instructions_and_model(
        self,
        *,
        tenant_id: UUID,
        request: ConversationRequest,
    ) -> tuple[str, str]:
        agent = await self.agents_repository.get_agent(request.agent_id)
        if agent is None:
            raise DomainValidationException(message="agent_not_found")
        if agent.tenant_id != tenant_id:
            raise DomainValidationException(message="agent_tenant_mismatch")
        active_version_id = await self.agents_repository.get_active_agent_version_id(
            request.agent_id
        )
        if active_version_id is None:
            raise DomainValidationException(message="agent_active_version_not_found")
        agent_version = await self.agents_repository.get_agent_version(active_version_id)
        if agent_version is None:
            raise DomainValidationException(message="agent_version_not_found")
        instructions = (agent_version.system_prompt or "").strip()
        if request.user_prompt_id is not None:
            selected_prompt = await self.user_prompts_repository.get_by_id(
                tenant_id=tenant_id,
                user_prompt_id=request.user_prompt_id,
            )
            if selected_prompt is not None:
                prompt_text = selected_prompt.content.strip()
                if prompt_text:
                    instructions = f"{instructions}\n\n{prompt_text}".strip()
        model = settings.OPENAI_CONVERSATION_MODEL
        return instructions, model

    async def _run_direct(
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
        session_id = request.session_id or uuid4()
        correlation_id = request.correlation_id or uuid4()
        interaction_id: UUID | None = None
        await queue.put(
            ConversationEvent(
                event_type=SSEEventType.CONNECTED,
                payload={
                    "session_id": str(session_id),
                    "correlation_id": str(correlation_id),
                    "interaction_id": None,
                },
            )
        )

        final_text = ""
        idempotency_key = request_id or str(correlation_id)
        idem_store_key = self.idempotency.build_key(
            tenant_id=tenant_id,
            endpoint="/core/v1/conversations",
            idempotency_key=idempotency_key,
        )
        try:
            cached = await self.idempotency.get(idem_store_key)
            if isinstance(cached, dict) and cached.get("status") == "DONE":
                cached_payload = cached.get("payload") or {}
                await queue.put(
                    ConversationEvent(
                        event_type=SSEEventType.DONE,
                        payload=dict(cached_payload),
                    )
                )
                await queue.put(None)
                return
            acquired = await self.idempotency.try_acquire(idem_store_key)
            if not acquired:
                raise DomainValidationException(message="idempotency_in_progress")
            await self.execution_repository.create_session(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=request.user_id,
            )
            interaction_id = await asyncio.wait_for(
                self.execution_repository.create_interaction(
                    session_id=session_id,
                    channel=str(channel),
                    payload=request.model_dump(mode="json"),
                    headers=headers,
                    metadata={
                        "tenant_id": str(tenant_id),
                        "agent_id": str(request.agent_id),
                        "conversation_mode": "direct_llm",
                    },
                    external_message_id=external_message_id,
                    request_id=request_id,
                    trace_id=trace_id,
                ),
                timeout=10.0,
            )
            user_input = (request.user_input or "").strip()
            if not user_input:
                raise DomainValidationException(message="user_input_required")
            instructions, model = await self._resolve_instructions_and_model(
                tenant_id=tenant_id,
                request=request,
            )
            mcp_cfg = get_conversation_mcp_config()
            mcp_tools: list[dict[str, str | dict[str, str]]] | None = None
            if mcp_cfg is not None:
                mcp_tools = [
                    {
                        "type": "mcp",
                        "server_label": "tenant-mcp",
                        "server_url": mcp_cfg.mcp_server_url,
                        "require_approval": "never",
                        "headers": {
                            "x-api-key": mcp_cfg.mcp_access_key,
                            "authorization": f"Bearer {mcp_cfg.outbound_api_key}",
                        },
                    }
                ]

            async def _on_openai_event(event: object) -> None:
                nonlocal final_text
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        final_text += delta
                        await queue.put(
                            ConversationEvent(
                                event_type=SSEEventType.CONTENT_DELTA,
                                payload={
                                    "delta": delta,
                                    "source_event_type": event_type,
                                },
                            )
                        )
                elif event_type == "response.tool_call.started":
                    await queue.put(
                        ConversationEvent(
                            event_type=SSEEventType.TOOL_PROGRESS,
                            payload={
                                "phase": "started",
                                "source_event_type": event_type,
                            },
                        )
                    )
                elif event_type == "response.tool_call.completed":
                    await queue.put(
                        ConversationEvent(
                            event_type=SSEEventType.TOOL_PROGRESS,
                            payload={
                                "phase": "completed",
                                "source_event_type": event_type,
                            },
                        )
                    )
                elif event_type == "response.error":
                    await queue.put(
                        ConversationEvent(
                            event_type=SSEEventType.ERROR,
                            payload={
                                "code": "openai_stream_error",
                                "message": str(getattr(event, "error", "openai_stream_error")),
                                "correlation_id": str(correlation_id),
                                "trace_id": trace_id,
                            },
                        )
                    )

            llm_result = await self.openai_provider.infer_conversation_stream(
                model=model,
                instructions=instructions,
                user_input=user_input,
                temperature=0.2,
                user_id=request.user_id,
                conversation_key=str(session_id),
                mcp_tools=mcp_tools,
                store=False,
                on_openai_event=_on_openai_event,
            )
            result_content = llm_result.output.get("content")
            if isinstance(result_content, str) and result_content.strip():
                final_text = result_content
            if interaction_id is not None:
                await self.execution_repository.update_interaction_result(
                    interaction_id=interaction_id,
                    output={"content": final_text},
                    status="SUCCESS",
                    error=None,
                )
            await queue.put(
                ConversationEvent(
                    event_type=SSEEventType.DONE,
                    payload={
                        "session_id": str(session_id),
                        "correlation_id": str(correlation_id),
                        "final_text": final_text,
                    },
                )
            )
            await self.idempotency.set_result(
                idem_store_key,
                {
                    "status": "DONE",
                    "payload": {
                        "session_id": str(session_id),
                        "correlation_id": str(correlation_id),
                        "final_text": final_text,
                    },
                },
            )
            await queue.put(None)
        except Exception as exc:
            await self.idempotency.set_result(
                idem_store_key,
                {"status": "FAILED", "error": {"message": str(exc)}},
            )
            if interaction_id is not None:
                await self.execution_repository.update_interaction_result(
                    interaction_id=interaction_id,
                    output={},
                    status="FAILED",
                    error={"message": str(exc)},
                )
            await queue.put(
                ConversationEvent(
                    event_type=SSEEventType.ERROR,
                    payload={
                        "code": "conversation_turn_failed",
                        "message": "conversation_turn_failed",
                        "correlation_id": str(correlation_id),
                        "trace_id": trace_id,
                    },
                )
            )
            await queue.put(None)

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
            self._run_direct(
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
