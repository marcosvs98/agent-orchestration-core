from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.agents.schemas.agents import PersonaConfig
from domain.execution.services.agent_runtime.definition import AgentDefinition
from domain.tools.services.agent_tool_catalog import AgentToolBinding


@pytest.fixture
def tracer() -> MagicMock:
    tracer = MagicMock()
    tracer.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return tracer


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


def build_tool(name: str) -> AgentToolBinding:
    return AgentToolBinding(
        function_name=name,
        tool_id=uuid4(),
        tool_config_id=uuid4(),
        tool_name=name,
        description=f"{name} tool",
        request_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )


def build_definition(
    tools: list[AgentToolBinding], agent_id: UUID | None = None
) -> AgentDefinition:
    return AgentDefinition(
        agent_id=agent_id or uuid4(),
        agent_name="researcher",
        agent_version_id=uuid4(),
        system_prompt="You research things.",
        persona_config=PersonaConfig(),
        model_name="gpt-4.1",
        ai_execution_policy_version_id=uuid4(),
        billing_policy_version_id=uuid4(),
        tools=tools,
    )


def agents_repository_for(tenant_id: UUID, known_agent_ids: set[UUID] | None = None) -> MagicMock:
    repository = MagicMock()

    async def _get_agent(agent_id: UUID) -> Any:
        if known_agent_ids is not None and agent_id not in known_agent_ids:
            return None
        return MagicMock(agent_id=agent_id, tenant_id=tenant_id)

    repository.get_agent = AsyncMock(side_effect=_get_agent)
    return repository
