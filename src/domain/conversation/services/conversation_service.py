from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

from fastapi.sse import ServerSentEvent

import settings
from adapters.mcp.conversation_mcp_context import get_conversation_mcp_config
from adapters.observability.logging import get_logger
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.conversation.ports.service import ConversationServicePort
from domain.conversation.schemas.conversation import (
    ConversationEvent,
    ConversationRequest,
    SSEEventType,
)
from domain.conversation.services.conversation_mcp_tools import build_conversation_mcp_tools
from domain.conversation.services.conversation_turn_assembler import ConversationTurnAssembler
from domain.conversation.services.sse_writer import SSEWriter
from domain.conversation.utils.message_history import parse_message_history
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import Channel
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.schemas.llm import LLMResult
from domain.user_prompts.repositories.user_prompts_repository import (
    UserPromptsRepository,
)
from exceptions.service_exceptions import DomainValidationException

logger = get_logger(__name__)


class ConversationService(ConversationServicePort):
    def __init__(
        self,
        openai_provider: OpenAIProviderAdapter,
        idempotency: IdempotencyService,
        execution_repository: ExecutionRepository,
        agents_repository: AgentsRepository,
        user_prompts_repository: UserPromptsRepository,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.openai_provider = openai_provider
        self.idempotency = idempotency
        self.execution_repository = execution_repository
        self.agents_repository = agents_repository
        self.user_prompts_repository = user_prompts_repository
        self.tracer = tracer
        self.turn_assembler = ConversationTurnAssembler(
            agents_repository=agents_repository,
            user_prompts_repository=user_prompts_repository,
        )

    def _build_structured_error(
        self,
        exc: Exception,
        *,
        model: str,
        has_mcp_tools: bool,
        has_message_history: bool,
    ) -> dict[str, object]:
        if isinstance(exc, DomainValidationException):
            error_code = exc.message or "domain_validation_error"
            provider_errors = [str(item) for item in exc.errors()]
        else:
            error_code = type(exc).__name__
            provider_errors = [type(exc).__name__]
        payload_preview: dict[str, object] = {
            "has_mcp_tools": has_mcp_tools,
            "has_message_history": has_message_history,
        }
        if model:
            payload_preview["model"] = model
        return {
            "message": error_code,
            "code": error_code,
            "details": {
                "type": type(exc).__name__,
                "provider_errors": provider_errors,
                "payload_preview": payload_preview,
            },
        }

    async def _run_direct(
        self,
        *,
        tenant_id: UUID,
        canonical_principal_id: str,
        end_user_id: str,
        end_user_authorization: str | None,
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
        event_counts: dict[str, int] = {
            "connected": 1,
            "content_delta": 0,
            "tool_progress_started": 0,
            "tool_progress_completed": 0,
            "done": 0,
            "error": 0,
        }
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
        scoped_idempotency_key = f"{end_user_id}:{idempotency_key}"
        idem_store_key = self.idempotency.build_key(
            tenant_id=tenant_id,
            endpoint="/core/v1/conversations",
            idempotency_key=scoped_idempotency_key,
        )
        model = ""
        mcp_tools: list[dict[str, str | dict[str, str]]] = []
        message_history: list[dict[str, str]] = []
        parsed_trace_id: UUID | None = None
        if trace_id:
            try:
                parsed_trace_id = UUID(trace_id)
            except ValueError:
                parsed_trace_id = None
        conversation_trace = self.tracer.start_conversation_trace(
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=end_user_id,
            correlation_id=correlation_id,
            trace_id=parsed_trace_id,
            agent_id=request.agent_id,
            channel=str(channel),
            external_message_id=external_message_id,
            external_request_id=request_id,
            interaction_id=interaction_id,
        )
        canonical_trace_id = str(conversation_trace.trace_id)
        with self.tracer.conversation(
            trace=conversation_trace,
            name="domain.conversation.sse.turn",
            input={
                "tenant_id": str(tenant_id),
                "principal_id": canonical_principal_id,
                "end_user_id": end_user_id,
                "session_id": str(session_id),
                "correlation_id": str(correlation_id),
                "agent_id": str(request.agent_id),
                "channel": str(channel),
                "request_id": request_id,
                "external_message_id": external_message_id,
                "trace_id": canonical_trace_id,
                "has_metadata": bool(request.metadata),
                "has_selected_user_prompt": request.user_prompt_id is not None,
            },
        ) as turn_observation:
            try:
                cached = await self.idempotency.get(idem_store_key)
                if isinstance(cached, dict) and cached.get("status") == "DONE":
                    cached_payload = cached.get("payload") or {}
                    event_counts["done"] += 1
                    await queue.put(
                        ConversationEvent(
                            event_type=SSEEventType.DONE,
                            payload=dict(cached_payload),
                        )
                    )
                    await queue.put(None)
                    turn_observation.success(
                        output={
                            "status": "success",
                            "cached": True,
                            "interaction_id": None,
                            "event_counts": event_counts,
                        },
                        metadata={
                            "model_alias": model or settings.OPENAI_CONVERSATION_MODEL,
                            "has_mcp_tools": False,
                            "has_message_history": False,
                        },
                    )
                    return
                acquired = await self.idempotency.try_acquire(idem_store_key)
                if not acquired:
                    raise DomainValidationException(message="idempotency_in_progress")
                mcp_cfg = get_conversation_mcp_config()
                if mcp_cfg is not None:
                    mcp_tools = build_conversation_mcp_tools(
                        mcp_cfg,
                        end_user_authorization=end_user_authorization,
                    )
                try:
                    message_history = parse_message_history(request.metadata)
                except ValueError as exc:
                    raise DomainValidationException(message=str(exc)) from exc
                await self.execution_repository.create_session(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=end_user_id,
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
                            "principal_id": canonical_principal_id,
                        },
                        external_message_id=external_message_id,
                        request_id=request_id,
                        trace_id=canonical_trace_id,
                    ),
                    timeout=10.0,
                )
                conversation_trace.interaction_id = interaction_id
                turn_observation.update(metadata={"interaction_id": str(interaction_id)})
                model = settings.OPENAI_CONVERSATION_MODEL
                with self.tracer.observe(
                    as_type="chain",
                    name="domain.conversation.prompt.assemble",
                    input={
                        "tenant_id": str(tenant_id),
                        "agent_id": str(request.agent_id),
                        "model_alias": model,
                        "history_message_count": len(message_history),
                        "tool_count": len(mcp_tools),
                        "has_selected_user_prompt": request.user_prompt_id is not None,
                    },
                    metadata={
                        "tenant_id": str(tenant_id),
                        "agent_id": str(request.agent_id),
                    },
                ) as prompt_observation:
                    turn_spec = await self.turn_assembler.assemble(
                        tenant_id=tenant_id,
                        canonical_principal_id=canonical_principal_id,
                        request=request,
                        model_alias=model,
                        conversation_key=str(session_id),
                        mcp_tools=mcp_tools,
                        message_history=message_history,
                    )
                    prompt_observation.success(
                        output={
                            "status": "success",
                            "prompt_part_count": len(turn_spec.prompt_parts),
                            "history_mode": turn_spec.history_mode,
                            "has_tools": bool(turn_spec.tools),
                            "prompt_sources": [part.source for part in turn_spec.prompt_parts],
                            "prompt_roles": [part.role for part in turn_spec.prompt_parts],
                            "prompt_trust_levels": [
                                part.trust_level for part in turn_spec.prompt_parts
                            ],
                        },
                        metadata=turn_spec.trace_metadata,
                    )
                streaming_request = turn_spec.to_streaming_request()
                model = streaming_request.model_alias

                async def _on_openai_event(event: dict[str, object]) -> None:
                    nonlocal final_text
                    event_type_raw = event.get("type", "")
                    event_type = str(event_type_raw) if event_type_raw else ""
                    if event_type == "response.output_text.delta":
                        delta_raw = event.get("delta", "")
                        delta = str(delta_raw) if delta_raw else ""
                        if delta:
                            final_text += delta
                            event_counts["content_delta"] += 1
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
                        event_counts["tool_progress_started"] += 1
                        tool_call = event.get("tool_call")
                        tool_input: dict[str, Any] = {
                            "phase": "started",
                            "source_event_type": event_type,
                        }
                        for key in ("tool_call_id", "call_id", "item_id", "name", "tool_name"):
                            raw = event.get(key)
                            if isinstance(raw, str) and raw.strip():
                                tool_input[key] = raw.strip()
                        if isinstance(tool_call, dict):
                            for key in ("id", "call_id", "name"):
                                raw = tool_call.get(key)
                                if isinstance(raw, str) and raw.strip():
                                    tool_input[f"tool_call_{key}"] = raw.strip()
                        with self.tracer.observe(
                            as_type="span",
                            name="domain.conversation.openai.tool_call.started",
                            input=tool_input,
                        ):
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
                        event_counts["tool_progress_completed"] += 1
                        tool_call = event.get("tool_call")
                        completed_tool_input: dict[str, Any] = {
                            "phase": "completed",
                            "source_event_type": event_type,
                        }
                        for key in ("tool_call_id", "call_id", "item_id", "name", "tool_name"):
                            raw = event.get(key)
                            if isinstance(raw, str) and raw.strip():
                                completed_tool_input[key] = raw.strip()
                        if isinstance(tool_call, dict):
                            for key in ("id", "call_id", "name"):
                                raw = tool_call.get(key)
                                if isinstance(raw, str) and raw.strip():
                                    completed_tool_input[f"tool_call_{key}"] = raw.strip()
                        with self.tracer.observe(
                            as_type="span",
                            name="domain.conversation.openai.tool_call.completed",
                            input=completed_tool_input,
                        ):
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
                        event_counts["error"] += 1
                        error_code = "openai_stream_error"
                        error_data = event.get("error")
                        if isinstance(error_data, dict):
                            code_value = error_data.get("code")
                            if isinstance(code_value, str) and code_value:
                                error_code = code_value
                        with self.tracer.observe(
                            as_type="span",
                            name="domain.conversation.openai.response_error",
                            input={
                                "code": error_code,
                                "source_event_type": event_type,
                            },
                        ):
                            await queue.put(
                                ConversationEvent(
                                    event_type=SSEEventType.ERROR,
                                    payload={
                                        "code": error_code,
                                        "message": "openai_stream_error",
                                        "correlation_id": str(correlation_id),
                                        "trace_id": canonical_trace_id,
                                    },
                                )
                            )

                llm_result: LLMResult | None = None
                with self.tracer.observe(
                    as_type="generation",
                    name="domain.conversation.openai.stream",
                    input={
                        "model": streaming_request.model_alias,
                        "history_mode": streaming_request.history_mode,
                        "temperature": streaming_request.temperature,
                        "tool_count": len(streaming_request.tools),
                        "tools": [
                            {
                                "type": tool.get("type"),
                                "server_label": tool.get("server_label"),
                                "require_approval": tool.get("require_approval"),
                            }
                            for tool in streaming_request.tools
                            if isinstance(tool, dict)
                        ],
                        "input_messages": [
                            message.model_dump(mode="json")
                            for message in streaming_request.input_messages
                        ],
                        "conversation_key": streaming_request.conversation_key,
                        "user_id": streaming_request.principal_id,
                    },
                    metadata={
                        "history_mode": streaming_request.history_mode,
                        "has_tools": bool(streaming_request.tools),
                        "tool_count": len(streaming_request.tools),
                    },
                    model=model,
                    model_parameters={"temperature": streaming_request.temperature},
                ) as generation_observation:
                    try:
                        llm_result = await self.openai_provider.infer_streaming_request(
                            request=streaming_request,
                            on_openai_event=_on_openai_event,
                        )
                    except Exception as exc:
                        provider_error = type(exc).__name__
                        if isinstance(exc, DomainValidationException):
                            errs = exc.errors()
                            provider_error = str(errs[0]) if errs else exc.message
                        generation_observation.error(
                            error_type=type(exc).__name__,
                            error_message=str(provider_error),
                            output={"status": "error", "code": provider_error},
                        )
                        raise
                    result_content = llm_result.output.get("content")
                    if isinstance(result_content, str) and result_content.strip():
                        final_text = result_content
                    usage_details = {
                        "prompt_tokens": llm_result.token_usage.get("input_tokens", 0),
                        "completion_tokens": llm_result.token_usage.get("output_tokens", 0),
                        "total_tokens": llm_result.token_usage.get("total_tokens", 0),
                    }
                    raw_response_id: str | None = None
                    if isinstance(llm_result.raw_output, dict):
                        raw_value = llm_result.raw_output.get("id")
                        if isinstance(raw_value, str) and raw_value.strip():
                            raw_response_id = raw_value.strip()
                    generation_observation.success(
                        output={
                            "status": "success",
                            "content_length": len(final_text),
                            "response_id": raw_response_id,
                        },
                        usage_details=usage_details,
                        metadata={
                            "latency_ms": llm_result.latency_ms,
                            "model_alias": llm_result.model_alias,
                            "history_mode": streaming_request.history_mode,
                            "has_tools": bool(streaming_request.tools),
                            "tool_count": len(streaming_request.tools),
                        },
                    )
                if interaction_id is not None:
                    await self.execution_repository.update_interaction_result(
                        interaction_id=interaction_id,
                        output={"content": final_text},
                        status="SUCCESS",
                        error=None,
                    )
                event_counts["done"] += 1
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
                turn_observation.success(
                    output={
                        "status": "success",
                        "cached": False,
                        "interaction_id": str(interaction_id)
                        if interaction_id is not None
                        else None,
                        "final_text_length": len(final_text),
                        "event_counts": event_counts,
                    },
                    metadata={
                        "model_alias": model,
                        "has_mcp_tools": bool(mcp_tools),
                        "has_message_history": bool(message_history),
                    },
                )
            except Exception as exc:
                structured_error = self._build_structured_error(
                    exc,
                    model=model,
                    has_mcp_tools=bool(mcp_tools),
                    has_message_history=bool(message_history),
                )
                error_code = str(structured_error["code"])
                details_raw = structured_error.get("details")
                provider_errors: list[object] = []
                if isinstance(details_raw, dict):
                    raw_provider_errors = details_raw.get("provider_errors")
                    if isinstance(raw_provider_errors, list):
                        provider_errors = raw_provider_errors
                logger.exception(
                    "conversation_direct_llm_turn_failed",
                    trace_id=canonical_trace_id,
                    correlation_id=str(correlation_id),
                    session_id=str(session_id),
                    interaction_id=str(interaction_id) if interaction_id is not None else None,
                    tenant_id=str(tenant_id),
                    agent_id=str(request.agent_id),
                    error_code=error_code,
                    error_type=type(exc).__name__,
                    provider_errors=provider_errors,
                )
                await self.idempotency.set_result(
                    idem_store_key,
                    {"status": "FAILED", "error": structured_error},
                )
                if interaction_id is not None:
                    await self.execution_repository.update_interaction_result(
                        interaction_id=interaction_id,
                        output={},
                        status="FAILED",
                        error=structured_error,
                    )
                error_payload: dict[str, str | None] = {
                    "code": "conversation_turn_failed",
                    "message": "conversation_turn_failed",
                    "error_code": error_code,
                    "correlation_id": str(correlation_id),
                    "trace_id": canonical_trace_id,
                }
                if interaction_id is not None:
                    error_payload["debug_id"] = str(interaction_id)
                event_counts["error"] += 1
                await queue.put(
                    ConversationEvent(
                        event_type=SSEEventType.ERROR,
                        payload=error_payload,
                    )
                )
                await queue.put(None)
                turn_observation.error(
                    error_type=type(exc).__name__,
                    error_message=error_code,
                    output={
                        "status": "error",
                        "error_code": error_code,
                        "interaction_id": str(interaction_id)
                        if interaction_id is not None
                        else None,
                        "event_counts": event_counts,
                    },
                    metadata={
                        "model_alias": model,
                        "has_mcp_tools": bool(mcp_tools),
                        "has_message_history": bool(message_history),
                    },
                )

    async def execute_turn(
        self,
        *,
        tenant_id: UUID,
        canonical_principal_id: str,
        end_user_id: str,
        end_user_authorization: str | None,
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
                canonical_principal_id=canonical_principal_id,
                end_user_id=end_user_id,
                end_user_authorization=end_user_authorization,
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
