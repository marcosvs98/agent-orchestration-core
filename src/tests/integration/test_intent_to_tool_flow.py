from __future__ import annotations

import pytest
from uuid import uuid4

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.llm.services.context_builder import ContextBuilder
from domain.llm.schemas.contexts import (
    IntentDetectionContext,
    SlotFillingContext,
    ResponseFormattingContext,
)
from domain.tools.repositories.tools_repository import ToolsRepository


@pytest.mark.asyncio
async def test_context_builder_builds_intent_context(
    agents_repository: AgentsRepository,
    tools_repository: ToolsRepository,
):
    context_builder = ContextBuilder(agents_repository, tools_repository)
    
    agent_version_id = uuid4()
    user_input = "Quero consultar meu saldo"
    
    context = await context_builder.build_intent_context(
        agent_version_id=agent_version_id,
        user_input=user_input,
    )
    
    assert isinstance(context, IntentDetectionContext)
    assert context.user_input == user_input
    assert isinstance(context.persona, PersonaConfig)


@pytest.mark.asyncio
async def test_context_builder_builds_slot_filling_context(
    agents_repository: AgentsRepository,
    tools_repository: ToolsRepository,
):
    context_builder = ContextBuilder(agents_repository, tools_repository)
    
    agent_version_id = uuid4()
    intent = "consult_balance"
    tool_config_id = uuid4()
    
    context = await context_builder.build_slot_filling_context(
        agent_version_id=agent_version_id,
        intent=intent,
        tool_config_id=tool_config_id,
    )
    
    assert isinstance(context, SlotFillingContext)
    assert context.intent == intent
    assert context.tool_config_id == tool_config_id
    assert isinstance(context.persona, PersonaConfig)
    assert isinstance(context.request_schema, dict)


@pytest.mark.asyncio
async def test_context_builder_builds_response_formatting_context(
    agents_repository: AgentsRepository,
    tools_repository: ToolsRepository,
):
    context_builder = ContextBuilder(agents_repository, tools_repository)
    
    agent_version_id = uuid4()
    tool_response = {"balance": 1000.0}
    original_intent = "consult_balance"
    
    context = await context_builder.build_response_formatting_context(
        agent_version_id=agent_version_id,
        tool_response=tool_response,
        original_intent=original_intent,
    )
    
    assert isinstance(context, ResponseFormattingContext)
    assert context.tool_response == tool_response
    assert context.original_intent == original_intent
    assert isinstance(context.persona, PersonaConfig)
