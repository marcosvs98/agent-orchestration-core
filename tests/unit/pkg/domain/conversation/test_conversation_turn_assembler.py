from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.conversation.schemas.conversation import ConversationRequest
from domain.conversation.services.conversation_turn_assembler import (
    ConversationTurnAssembler,
)
from exceptions.service_exceptions import DomainValidationException


@pytest.mark.asyncio
async def test_assemble_orders_prompt_parts() -> None:
    tenant_id = uuid4()
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Pergunta atual",
        user_prompt_id=uuid4(),
    )
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(return_value=AsyncMock(system_prompt="System"))
    user_prompts_repository = AsyncMock()
    user_prompts_repository.get_by_id = AsyncMock(
        return_value=AsyncMock(content="Selected", version=3)
    )
    assembler = ConversationTurnAssembler(
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )

    spec = await assembler.assemble(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        request=request,
        model_alias="gpt-4.1",
        conversation_key="tenant:session",
        mcp_tools=[],
        message_history=[
            {"role": "user", "content": "Hist user"},
            {"role": "assistant", "content": "Hist assistant"},
        ],
    )

    assert [part.source for part in spec.prompt_parts] == [
        "agent_system_prompt",
        "runtime_rules",
        "selected_user_prompt",
        "message_history",
        "message_history",
        "current_user_input",
    ]
    assert spec.history_mode == "manual"
    streaming_request = spec.to_streaming_request()
    assert [msg.model_dump(mode="json") for msg in streaming_request.input_messages] == [
        {"role": "system", "content": "System"},
        {"role": "developer", "content": assembler._RUNTIME_RULES},
        {"role": "developer", "content": "Selected"},
        {"role": "user", "content": "Hist user"},
        {"role": "assistant", "content": "Hist assistant"},
        {"role": "user", "content": "Pergunta atual"},
    ]


@pytest.mark.asyncio
async def test_assemble_fails_when_user_prompt_not_found() -> None:
    tenant_id = uuid4()
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Pergunta atual",
        user_prompt_id=uuid4(),
    )
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(return_value=AsyncMock(system_prompt="System"))
    user_prompts_repository = AsyncMock()
    user_prompts_repository.get_by_id = AsyncMock(return_value=None)
    assembler = ConversationTurnAssembler(
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )

    with pytest.raises(DomainValidationException, match="user_prompt_not_found"):
        await assembler.assemble(
            tenant_id=tenant_id,
            canonical_principal_id="user-1",
            request=request,
            model_alias="gpt-4.1",
            conversation_key="tenant:session",
            mcp_tools=[],
            message_history=[],
        )


@pytest.mark.asyncio
async def test_assemble_uses_provider_conversation_without_history() -> None:
    tenant_id = uuid4()
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="Pergunta atual",
    )
    agents_repository = AsyncMock()
    agents_repository.get_agent = AsyncMock(return_value=AsyncMock(tenant_id=tenant_id))
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    agents_repository.get_agent_version = AsyncMock(return_value=AsyncMock(system_prompt="System"))
    user_prompts_repository = AsyncMock()
    assembler = ConversationTurnAssembler(
        agents_repository=agents_repository,
        user_prompts_repository=user_prompts_repository,
    )

    spec = await assembler.assemble(
        tenant_id=tenant_id,
        canonical_principal_id="user-1",
        request=request,
        model_alias="gpt-4.1",
        conversation_key="tenant:session",
        mcp_tools=[],
        message_history=[],
    )

    assert spec.history_mode == "provider_conversation"
    assert spec.conversation_key == "tenant:session"
