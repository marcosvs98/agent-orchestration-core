from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from domain.conversation.schemas.conversation import ConversationRequest
from domain.conversation.services.conversation_service import ConversationService
from domain.execution.schemas.execution import Channel
from exceptions.service_exceptions import DomainValidationException


@pytest.mark.asyncio
async def test_execute_turn_streams_deltas_and_done() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()

    async def _fake_infer_conversation_stream(**kwargs):
        on_openai_event = kwargs["on_openai_event"]
        event_delta = SimpleNamespace(type="response.output_text.delta", delta="Ola")
        event_completed = SimpleNamespace(type="response.completed")
        await on_openai_event(event_delta)
        await on_openai_event(event_completed)
        return SimpleNamespace(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_conversation_stream = AsyncMock(
        side_effect=_fake_infer_conversation_stream
    )
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
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

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        session_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos em maio de 2026",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
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
async def test_execute_turn_passes_user_jwt_in_mcp_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    from adapters.mcp.conversation_mcp_context import set_conversation_mcp_config
    from domain.conversation.schemas.mcp_config import TenantMcpConfig

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

    captured: dict[str, object] = {}

    async def _fake_infer_conversation_stream(**kwargs):
        captured.update(kwargs)
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event(
            SimpleNamespace(type="response.output_text.delta", delta="Ola")
        )
        return SimpleNamespace(output={"content": "Ola"})

    openai_provider = AsyncMock()
    openai_provider.infer_conversation_stream = AsyncMock(
        side_effect=_fake_infer_conversation_stream
    )
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=session_id,
        user_id="user-1",
        user_input="Quanto gastei esse mes?",
        metadata={"uora_end_user_authorization": "Bearer user-jwt"},
    )

    try:
        stream = await service.execute_turn(
            tenant_id=tenant_id,
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
        from adapters.mcp.conversation_mcp_context import _CONVERSATION_MCP_CONFIG

        _CONVERSATION_MCP_CONFIG.reset(tok)

    mcp_tools = captured.get("mcp_tools")
    assert isinstance(mcp_tools, list)
    assert mcp_tools[0]["headers"]["authorization"] == "Bearer user-jwt"


@pytest.mark.asyncio
async def test_execute_turn_passes_message_history_to_openai() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    captured: dict[str, object] = {}

    async def _fake_infer_conversation_stream(**kwargs):
        captured.update(kwargs)
        on_openai_event = kwargs["on_openai_event"]
        await on_openai_event(
            SimpleNamespace(type="response.output_text.delta", delta="Fatura")
        )
        return SimpleNamespace(output={"content": "Fatura"})

    openai_provider = AsyncMock()
    openai_provider.infer_conversation_stream = AsyncMock(
        side_effect=_fake_infer_conversation_stream
    )
    execution_repository = AsyncMock()
    execution_repository.create_interaction = AsyncMock(return_value=uuid4())
    execution_repository.update_interaction_result = AsyncMock()
    idempotency = AsyncMock()
    idempotency.build_key = lambda **_: "idem-key"
    idempotency.get = AsyncMock(return_value=None)
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.set_result = AsyncMock()
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
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

    assert captured["message_history"] == [
        {"role": "user", "content": "Cartão e fatura"},
        {"role": "assistant", "content": "Escolha o cartão VISA INFINITE"},
        {"role": "user", "content": "VISA INFINITE (final485d)"},
        {"role": "assistant", "content": "Limite total de R$40.000,00"},
    ]


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
    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos em maio de 2026",
    )
    stream = await service.execute_turn(
        tenant_id=tenant_id,
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


@pytest.mark.asyncio
async def test_execute_turn_persists_structured_error_and_sse_debug_id() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    interaction_id = uuid4()

    openai_provider = AsyncMock()
    openai_provider.infer_conversation_stream = AsyncMock(
        side_effect=DomainValidationException(
            "llm_provider_error",
            errors=["Error code: 424 - Failed Dependency"],
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
    agents_repository.get_agent = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-err",
        trace_id="trace-err",
        last_event_id=None,
    )

    events: list[tuple[str | None, object]] = []
    async for chunk in stream:
        events.append((chunk.event, chunk.data))

    error_events = [data for event, data in events if event == "error"]
    assert error_events
    error_payload = error_events[0]
    assert error_payload["code"] == "conversation_turn_failed"
    assert error_payload["message"] == "conversation_turn_failed"
    assert error_payload["error_code"] == "llm_provider_error"
    assert error_payload["debug_id"] == str(interaction_id)
    assert error_payload["trace_id"] == "trace-err"

    update_call = execution_repository.update_interaction_result.await_args.kwargs
    assert update_call["status"] == "FAILED"
    structured_error = update_call["error"]
    assert structured_error["code"] == "llm_provider_error"
    assert structured_error["details"]["provider_errors"] == [
        "Error code: 424 - Failed Dependency"
    ]
    assert "payload_preview" in structured_error["details"]


@pytest.mark.asyncio
async def test_execute_turn_persists_structured_error_and_sse_debug_id() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    interaction_id = uuid4()

    openai_provider = AsyncMock()
    openai_provider.infer_conversation_stream = AsyncMock(
        side_effect=DomainValidationException(
            "llm_provider_error",
            errors=["Error code: 424 - Failed Dependency"],
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
    agents_repository.get_agent = AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(system_prompt="System prompt")
    )
    user_prompts_repository = AsyncMock()

    service = ConversationService(
        openai_provider=openai_provider,
        idempotency=idempotency,
        execution_repository=execution_repository,
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )
    request = ConversationRequest(
        agent_id=agent_id,
        session_id=uuid4(),
        user_id="user-1",
        user_input="Mostre meus gastos",
    )

    stream = await service.execute_turn(
        tenant_id=tenant_id,
        request=request,
        channel=Channel.HTTP,
        headers={},
        external_message_id=None,
        request_id="req-err",
        trace_id="trace-err",
        last_event_id=None,
    )

    events: list[tuple[str | None, object]] = []
    async for chunk in stream:
        events.append((chunk.event, chunk.data))

    error_events = [data for event, data in events if event == "error"]
    assert error_events
    error_payload = error_events[0]
    assert error_payload["code"] == "conversation_turn_failed"
    assert error_payload["message"] == "conversation_turn_failed"
    assert error_payload["error_code"] == "llm_provider_error"
    assert error_payload["debug_id"] == str(interaction_id)
    assert error_payload["trace_id"] == "trace-err"

    update_call = execution_repository.update_interaction_result.await_args.kwargs
    assert update_call["status"] == "FAILED"
    structured_error = update_call["error"]
    assert structured_error["code"] == "llm_provider_error"
    assert structured_error["details"]["provider_errors"] == [
        "Error code: 424 - Failed Dependency"
    ]
    assert "payload_preview" in structured_error["details"]
