"""Agent Card: how a peer agent discovers what an AOC agent can do."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.agents.services.agent_card_service import AgentCardService
from exceptions.service_exceptions import NotFoundServiceException


def _service(
    tenant_id,
    *,
    agent=None,
    active_version_id=None,
    agent_version=None,
    bindings=None,
    rows=None,
) -> AgentCardService:
    agents_repository = MagicMock()
    agents_repository.get_agent = AsyncMock(return_value=agent)
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=active_version_id)
    agents_repository.get_agent_version = AsyncMock(return_value=agent_version)

    tools_repository = MagicMock()
    tools_repository.list_tool_bindings_by_agent_version_id = AsyncMock(return_value=bindings or [])
    tools_repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock(
        return_value=rows or []
    )
    return AgentCardService(
        agents_repository=agents_repository,
        tools_repository=tools_repository,
        public_base_url="https://aoc.example.com/",
    )


@pytest.mark.asyncio
async def test_the_card_advertises_the_active_versions_tools_as_skills(tenant_id) -> None:
    agent_id = uuid4()
    agent_version_id = uuid4()
    tool_config_id = uuid4()
    service = _service(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="researcher"),
        active_version_id=agent_version_id,
        agent_version=SimpleNamespace(
            agent_version_id=agent_version_id,
            description="researches things",
            version_major=2,
            version_minor=1,
            version_patch=3,
        ),
        bindings=[SimpleNamespace(tool_config_id=tool_config_id)],
        rows=[
            (
                SimpleNamespace(
                    tool_config_id=tool_config_id,
                    config={"operation_id": "searchFlights", "summary": "finds flights"},
                ),
                SimpleNamespace(name="search"),
            )
        ],
    )

    card = await service.build_agent_card(tenant_id=tenant_id, agent_id=agent_id)

    assert card.name == "researcher"
    assert card.version == "2.1.3"
    assert card.url == f"https://aoc.example.com/core/v1/a2a/agents/{agent_id}"
    assert card.protocol_version == "0.3.0"
    assert [skill.id for skill in card.skills] == ["searchFlights"]
    assert card.skills[0].description == "finds flights"

    dumped = card.model_dump(mode="json")
    assert dumped["protocolVersion"] == "0.3.0"
    assert dumped["defaultInputModes"] == ["text/plain", "application/json"]
    assert dumped["capabilities"]["stateTransitionHistory"] is True
    assert dumped["securitySchemes"]["bearer"]["scheme"] == "bearer"


@pytest.mark.asyncio
async def test_an_agent_from_another_tenant_has_no_card(tenant_id) -> None:
    agent_id = uuid4()
    service = _service(
        tenant_id, agent=SimpleNamespace(agent_id=agent_id, tenant_id=uuid4(), name="x")
    )

    with pytest.raises(NotFoundServiceException, match="agent_not_found"):
        await service.build_agent_card(tenant_id=tenant_id, agent_id=agent_id)


@pytest.mark.asyncio
async def test_an_agent_without_an_active_version_has_no_card(tenant_id) -> None:
    agent_id = uuid4()
    service = _service(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="x"),
        active_version_id=None,
    )

    with pytest.raises(NotFoundServiceException, match="agent_active_version_not_found"):
        await service.build_agent_card(tenant_id=tenant_id, agent_id=agent_id)
