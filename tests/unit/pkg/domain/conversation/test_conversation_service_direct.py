from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from domain.llm.schemas.llm import LLMResult

from adapters.mcp.conversation_mcp_context import (
    _CONVERSATION_MCP_CONFIG,
    set_conversation_mcp_config,
)
from domain.conversation.schemas.conversation import ConversationRequest
from domain.conversation.schemas.mcp_config import TenantMcpConfig
from domain.conversation.services.conversation_service import ConversationService
from domain.execution.schemas.execution import Channel
from domain.llm.schemas.openai_streaming import OpenAIStreamingRequest
from exceptions.service_exceptions import DomainValidationException


class _TraceHandle:
    def __init__(self) -> None:
        self.update_calls: list[dict[str, Any]] = []
        self.success_calls: list[dict[str, Any]] = []
        self.error_calls: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)

    def success(
        self,
        *,
        output: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        payload: dict[str, Any] = {"output": output, "metadata": metadata}
        payload.update(kwargs)
        self.success_calls.append(payload)

    def error(
        self,
        *,
        error_type: str,
        error_message: str,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "error_type": error_type,
            "error_message": error_message,
            "output": output,
            "metadata": metadata,
        }
        payload.update(kwargs)
        self.error_calls.append(payload)


class _TraceRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.handles: list[_TraceHandle] = []
        self.start_conversation_trace_calls: list[dict[str, Any]] = []

    def start_conversation_trace(self, **kwargs: Any) -> Any:
        self.start_conversation_trace_calls.append(kwargs)
        trace_id = kwargs.get("trace_id")
        if trace_id is None:
            trace_id = uuid4()
        return SimpleNamespace(
            trace_id=trace_id,
            tenant_id=kwargs.get("tenant_id"),
            session_id=kwargs.get("session_id"),
            user_id=kwargs.get("user_id"),
            correlation_id=kwargs.get("correlation_id"),
            agent_id=kwargs.get("agent_id"),
            channel=kwargs.get("channel"),
            external_message_id=kwargs.get("external_message_id"),
            interaction_id=kwargs.get("interaction_id"),
            root_observation_id=None,
        )

    @contextmanager
    def conversation(self, **kwargs: Any) -> Iterator[_TraceHandle]:
        self.calls.append(
            {
                "as_type": "span",
                "name": kwargs.get("name"),
                "input": kwargs.get("input"),
                "trace": kwargs.get("trace"),
            }
        )
        handle = _TraceHandle()
        self.handles.append(handle)
        yield handle

    @contextmanager
    def observe(self, **kwargs: Any) -> Iterator[_TraceHandle]:
        self.calls.append(kwargs)
        handle = _TraceHandle()
        self.handles.append(handle)
        yield handle


@pytest.mark.asyncio
async def test_execute_turn_streams_deltas_and_done() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        on_openai_event = kwargs["on_openai_event"]
        event_delta = {"type": "response.output_text.delta", "delta": "Ola"}
        event_completed = {"type": "response.completed"}
        await on_openai_event(event_delta)
        await on_openai_event(event_completed)
        return AsyncMock(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="user-1",
        user_input="Mostre meus gastos em maio de 2026",
        correlation_id=correlation_id,
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-1",
        trace_id="trace-1",
        last_event_id=None,
    )

    events: list[tuple[str | None, object]] = []
    async for chunk in stream:
        events.append((chunk.event, chunk.data))

    event_names = [name for name, _ in events]
    assert "connected" in event_names
    assert "content_delta" in event_names
    assert "done" in event_names
    observed_names = [call["name"] for call in tracer.calls]
    assert "domain.conversation.sse.turn" in observed_names
    assert "domain.conversation.prompt.assemble" in observed_names
    assert "domain.conversation.openai.stream" in observed_names
    assert tracer.start_conversation_trace_calls
    root_call = tracer.start_conversation_trace_calls[0]
    assert root_call["tenant_id"] == tenant_id
    assert root_call["session_id"] == session_id
    assert root_call["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_execute_turn_traces_tool_lifecycle_without_sensitive_data() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    trace = _TraceRecorder()

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event(
            {
                "type": "response.tool_call.started",
                "tool_call_id": "call-1",
                "name": "lookup",
                "headers": {"authorization": "Bearer secret"},
            }
        )
        await on_openai_event(
            {
                "type": "response.tool_call.completed",
                "tool_call_id": "call-1",
                "name": "lookup",
                "arguments": {"cpf": "12345678900"},
            }
        )
        await on_openai_event({"type": "response.output_text.delta", "delta": "ok"})
        await on_openai_event({"type": "response.completed"})
        return AsyncMock(
            output={"content": "ok"},
            token_usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            raw_output={"id": "resp-1"},
            model_alias="gpt-4.1",
            latency_ms=10,
        )

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=trace,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        user_id="user-1",
        user_input="Mostre meus gastos",
    )
    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-trace",
        trace_id=str(uuid4()),
        last_event_id=None,
    )
    async for _chunk in stream:
        pass
    observed_names = [call["name"] for call in trace.calls]
    assert "domain.conversation.openai.tool_call.started" in observed_names
    assert "domain.conversation.openai.tool_call.completed" in observed_names
    dump = str(trace.calls)
    assert "Bearer secret" not in dump
    assert "12345678900" not in dump


@pytest.mark.asyncio
async def test_execute_turn_emits_error_when_agent_not_found() -> None:
    tenant_id = uuid4()
    openai_provider = AsyncMock()
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=None)
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        session_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos em maio de 2026",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-2",
        trace_id="trace-2",
        last_event_id=None,
    )

    event_names: list[str | None] = []
    async for chunk in stream:
        event_names.append(chunk.event)
    assert "error" in event_names


@pytest.mark.asyncio
async def test_execute_turn_generation_trace_includes_real_messages_without_tool_headers() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    mcp_cfg = TenantMcpConfig(
        mcp_server_id=uuid4(),
        mcp_server_url="http://example.com/core/v1/mcp-servers/x/mcp",
        mcp_access_key="mcp-access-key",
        outbound_api_key="outbound-fallback",
    )
    tok = set_conversation_mcp_config(mcp_cfg)

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event({"type": "response.output_text.delta", "delta": "Ola"})
        await on_openai_event({"type": "response.completed"})
        return AsyncMock(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="user-1",
        user_input="Quanto gastei esse mes?",
    )

    try:
        stream = await service.execute_turn(
            tenant_id=tenant_id,
            canonical_principal_id="user-1",
            end_user_id="user-1",
            end_user_authorization="Token user-jwt",
            request=request,
            channel=Channel.HTTP,
            headers={},
            external_message_id=None,
            request_id="req-trace-gen",
            trace_id=str(uuid4()),
            last_event_id=None,
        )
        async for _chunk in stream:
            pass
    finally:
        _CONVERSATION_MCP_CONFIG.reset(tok)

    generation_calls = [
        call for call in tracer.calls if call.get("name") == "domain.conversation.openai.stream"
    ]
    assert generation_calls
    generation_input = generation_calls[0]["input"]
    assert generation_input["input_messages"]
    assert generation_input["input_messages"][-1]["content"] == "Quanto gastei esse mes?"
    assert generation_input["input_messages"][0]["content"] == "System prompt"
    for tool in generation_input.get("tools", []):
        assert "headers" not in tool
        assert "server_url" not in tool
    dump = str(generation_input)
    assert "mcp-access-key" not in dump
    assert "Token user-jwt" not in dump


@pytest.mark.asyncio
async def test_execute_turn_passes_user_jwt_in_mcp_headers() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    mcp_cfg = TenantMcpConfig(
        mcp_server_id=uuid4(),
        mcp_server_url="http://example.com/core/v1/mcp-servers/x/mcp",
        mcp_access_key="mcp-access-key",
        outbound_api_key="outbound-fallback",
    )
    tok = set_conversation_mcp_config(mcp_cfg)

    captured: dict[str, Any] = {}

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        captured.update(kwargs)
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event({"type": "response.output_text.delta", "delta": "Ola"})
        return AsyncMock(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="user-1",
        user_input="Quanto gastei esse mes?",
    )

    try:
        stream = await service.execute_turn(
            tenant_id=tenant_id,
            canonical_principal_id="user-1",
            end_user_id="user-1",
            end_user_authorization="Token user-jwt",
            request=request,
            channel=Channel.HTTP,
            headers={},
            external_message_id=None,
            request_id="req-mcp",
            trace_id="trace-mcp",
            last_event_id=None,
        )
        async for _chunk in stream:
            pass
    finally:
        _CONVERSATION_MCP_CONFIG.reset(tok)

    streaming_request_raw = captured.get("request")
    assert isinstance(streaming_request_raw, OpenAIStreamingRequest)
    mcp_tools = streaming_request_raw.tools
    assert isinstance(mcp_tools, list)
    assert mcp_tools[0]["headers"]["authorization"] == "Token user-jwt"


@pytest.mark.asyncio
async def test_execute_turn_passes_message_history_to_openai() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    captured: dict[str, Any] = {}

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        captured.update(kwargs)
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event({"type": "response.output_text.delta", "delta": "Fatura"})
        return AsyncMock(output={"content": "Fatura"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="user-1",
        user_input="Preciso de detalhes da fatura",
        metadata={
            "message_history": [
                {"role": "user", "content": "Cartão e fatura"},
                {"role": "assistant", "content": "Escolha o cartão VISA INFINITE"},
                {"role": "user", "content": "VISA INFINITE (final485d)"},
                {
                    "role": "assistant",
                    "content": "Limite total de R$40.000,00",
                },
            ]
        },
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-history",
        trace_id="trace-history",
        last_event_id=None,
    )
    async for _chunk in stream:
        pass

    streaming_request_raw = captured["request"]
    assert isinstance(streaming_request_raw, OpenAIStreamingRequest)
    input_messages = [
        message.model_dump(mode="json") for message in streaming_request_raw.input_messages
    ]
    assert input_messages[2:6] == [
        {"role": "user", "content": "Cartão e fatura"},
        {"role": "assistant", "content": "Escolha o cartão VISA INFINITE"},
        {"role": "user", "content": "VISA INFINITE (final485d)"},
        {"role": "assistant", "content": "Limite total de R$40.000,00"},
    ]
    assert input_messages[-1] == {"role": "user", "content": "Preciso de detalhes da fatura"}


@pytest.mark.asyncio
async def test_execute_turn_uses_canonical_principal_id_for_provider_user() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    captured: dict[str, Any] = {}

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        captured.update(kwargs)
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event({"type": "response.output_text.delta", "delta": "ok"})
        await on_openai_event({"type": "response.completed"})
        return AsyncMock(output={"content": "ok"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="end-user-1",
        user_input="Quero o resumo",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="service-principal",
        end_user_id="end-user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-principal",
        trace_id=str(uuid4()),
        last_event_id=None,
    )
    async for _chunk in stream:
        pass

    streaming_request_raw = captured["request"]
    assert isinstance(streaming_request_raw, OpenAIStreamingRequest)
    assert streaming_request_raw.principal_id == "service-principal"


@pytest.mark.asyncio
async def test_execute_turn_uses_cached_idempotent_result() -> None:
    tenant_id = uuid4()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(
        return_value={
            "status": "DONE",
            "payload": {
                "session_id": str(uuid4()),
                "correlation_id": str(uuid4()),
                "final_text": "cached-answer",
            },
        }
    )
    idempotency.try_acquire = AsyncMock(return_value=False)
    idempotency.set_result = AsyncMock()
    execution_repository = AsyncMock()
    agents_repository = AsyncMock()
    user_prompts_repository = AsyncMock()
    openai_provider = AsyncMock()
    tracer = _TraceRecorder()
    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos em maio de 2026",
    )
    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-3",
        trace_id="trace-3",
        last_event_id=None,
    )
    events: list[str | None] = []
    async for chunk in stream:
        events.append(chunk.event)
    assert events == ["connected", "done"]
    openai_provider.infer_streaming_request.assert_not_called()


@pytest.mark.asyncio
async def test_execute_turn_persists_structured_error_and_sse_debug_id() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    interaction_id = uuid4()
    trace_id = str(uuid4())

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(
        side_effect=DomainValidationException(
            "llm_provider_error",
            errors=["provider_failed_dependency"],
        )
    )
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=interaction_id)
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-err",
        trace_id=trace_id,
        last_event_id=None,
    )

    events: list[tuple[str | None, object]] = []
    async for chunk in stream:
        events.append((chunk.event, chunk.data))

    error_events = [data for event, data in events if event == "error"]
    assert error_events
    error_payload_raw = error_events[0]
    assert isinstance(error_payload_raw, dict)
    assert error_payload_raw["code"] == "conversation_turn_failed"
    assert error_payload_raw["message"] == "conversation_turn_failed"
    assert error_payload_raw["error_code"] == "llm_provider_error"
    assert error_payload_raw["debug_id"] == str(interaction_id)
    assert error_payload_raw["trace_id"] == trace_id

    update_call = execution_repository.update_interaction_result.await_args.kwargs
    assert update_call["status"] == "FAILED"
    structured_error = update_call["error"]
    assert structured_error["code"] == "llm_provider_error"
    assert structured_error["details"]["provider_errors"] == ["provider_failed_dependency"]
    assert "payload_preview" in structured_error["details"]


@pytest.mark.asyncio
async def test_execute_turn_rejects_forbidden_metadata_key() -> None:
    tenant_id = uuid4()
    openai_provider = AsyncMock()
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()
    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos",
        metadata={"tenant_id": "forged"},
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-4",
        trace_id="trace-4",
        last_event_id=None,
    )
    event_names: list[str | None] = []
    async for chunk in stream:
        event_names.append(chunk.event)
    assert "error" in event_names
    openai_provider.infer_streaming_request.assert_not_called()


@pytest.mark.asyncio
async def test_direct_path_skips_llm_executor() -> None:
    tenant_id = uuid4()

    async def _fake_infer_streaming_request(**kwargs: Any) -> Any:
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event({"type": "response.output_text.delta", "delta": "Ola"})
        return AsyncMock(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_streaming_request = AsyncMock(side_effect=_fake_infer_streaming_request)
    openai_provider.infer = AsyncMock()
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=AsyncMock(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()
    tracer = _TraceRecorder()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
        tracer=tracer,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        end_user_id="user-1",
        end_user_authorization=None,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-5",
        trace_id="trace-5",
        last_event_id=None,
    )
    async for _chunk in stream:
        pass

    openai_provider.infer_streaming_request.assert_awaited_once()
    openai_provider.infer.assert_not_called()


@pytest.mark.asyncio
async def test_direct_turn_is_written_to_the_usage_ledger():
    """The direct endpoint bypasses LLMExecutor, so it records its own spend (gap register §3)."""

    from decimal import Decimal

    service = ConversationService(
        openai_provider=AsyncMock(),
        idempotency=AsyncMock(),
        execution_repository=AsyncMock(),
        agents_repository=AsyncMock(),
        user_prompts_repository=AsyncMock(),
        tracer=AsyncMock(),
        cost_engine=SimpleNamespace(compute_cost=AsyncMock(return_value=0.0123)),
    )
    tenant_id, session_id = uuid4(), uuid4()

    await service._record_turn_usage(
        tenant_id=tenant_id,
        session_id=session_id,
        model="gpt-4.1",
        llm_result=LLMResult(
            output={},
            token_usage={"input_tokens": 90, "output_tokens": 20},
            latency_ms=640,
        ),
    )

    kwargs = service.execution_repository.record_llm_usage.await_args.kwargs
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["session_id"] == session_id
    assert kwargs["provider_model"] == "gpt-4.1"
    assert kwargs["task_type"] == "conversation_turn"
    assert kwargs["input_tokens"] == 90
    assert kwargs["output_tokens"] == 20
    assert kwargs["cost_usd"] == Decimal("0.0123")
    assert kwargs["flow_run_id"] is None


@pytest.mark.asyncio
async def test_absent_token_usage_records_zeroes_rather_than_failing():
    service = ConversationService(
        openai_provider=AsyncMock(),
        idempotency=AsyncMock(),
        execution_repository=AsyncMock(),
        agents_repository=AsyncMock(),
        user_prompts_repository=AsyncMock(),
        tracer=AsyncMock(),
    )

    await service._record_turn_usage(
        tenant_id=uuid4(),
        session_id=uuid4(),
        model="gpt-4.1",
        llm_result=LLMResult(output={}),
    )

    kwargs = service.execution_repository.record_llm_usage.await_args.kwargs
    assert kwargs["input_tokens"] == 0
    assert kwargs["output_tokens"] == 0
    assert kwargs["cost_usd"] is None


@pytest.mark.asyncio
async def test_ledger_write_failure_never_breaks_a_streamed_turn():
    """Accounting is best-effort; the turn has already been delivered to the client."""

    execution_repository = AsyncMock()
    execution_repository.record_llm_usage = AsyncMock(side_effect=RuntimeError("db down"))
    service = ConversationService(
        openai_provider=AsyncMock(),
        idempotency=AsyncMock(),
        execution_repository=execution_repository,
        agents_repository=AsyncMock(),
        user_prompts_repository=AsyncMock(),
        tracer=AsyncMock(),
    )

    await service._record_turn_usage(
        tenant_id=uuid4(),
        session_id=uuid4(),
        model="gpt-4.1",
        llm_result=LLMResult(output={}, token_usage={"input_tokens": 5, "output_tokens": 1}),
    )
