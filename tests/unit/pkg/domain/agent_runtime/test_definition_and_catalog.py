"""Resolving the agent definition a run executes against, and the tools it may offer.

A direct agent run must clear the same gates as a flow-driven one: active + published version,
published AI execution policy, active billing policy.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.common.schemas.versioning import VersionStatus
from domain.execution.services.agent_runtime.definition import AgentDefinitionResolver
from domain.tools.services.agent_tool_catalog import (
    AgentToolCatalog,
    normalize_tool_function_name,
    tool_request_schema,
)
from exceptions.service_exceptions import (
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


def _agent_version(**overrides) -> SimpleNamespace:
    fields = dict(
        agent_version_id=uuid4(),
        agent_id=uuid4(),
        status=VersionStatus.PUBLISHED.value,
        version_major=1,
        version_minor=0,
        version_patch=0,
        description="an agent",
        system_prompt="You help.",
        persona_config=None,
        ai_execution_policy_version_id=uuid4(),
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _resolver(
    tenant_id,
    *,
    agent=None,
    active_version_id=None,
    agent_version=None,
    policy_version=None,
    model=None,
    billing_policy_version_id=None,
    tools=None,
) -> AgentDefinitionResolver:
    agents_repository = MagicMock()
    agents_repository.get_agent = AsyncMock(return_value=agent)
    agents_repository.get_active_agent_version_id = AsyncMock(return_value=active_version_id)
    agents_repository.get_agent_version = AsyncMock(return_value=agent_version)

    execution_repository = MagicMock()
    execution_repository.get_ai_execution_policy_version = AsyncMock(return_value=policy_version)
    execution_repository.get_model = AsyncMock(return_value=model)
    execution_repository.get_active_billing_policy_version_id = AsyncMock(
        return_value=billing_policy_version_id
    )

    tool_catalog = MagicMock()
    tool_catalog.list_agent_version_tools = AsyncMock(return_value=tools or [])
    return AgentDefinitionResolver(
        agents_repository=agents_repository,
        execution_repository=execution_repository,
        tool_catalog=tool_catalog,
    )


def _happy_path(tenant_id):
    agent_id = uuid4()
    version = _agent_version(agent_id=agent_id)
    return (
        agent_id,
        version,
        _resolver(
            tenant_id,
            agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="researcher"),
            active_version_id=version.agent_version_id,
            agent_version=version,
            policy_version=SimpleNamespace(status=VersionStatus.PUBLISHED.value, model_id=uuid4()),
            model=SimpleNamespace(name="gpt-4.1"),
            billing_policy_version_id=uuid4(),
        ),
    )


@pytest.mark.asyncio
async def test_the_active_published_version_becomes_the_definition(tenant_id) -> None:
    agent_id, version, resolver = _happy_path(tenant_id)

    definition = await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)

    assert definition.agent_id == agent_id
    assert definition.agent_version_id == version.agent_version_id
    assert definition.model_name == "gpt-4.1"
    assert definition.system_prompt_hash() is not None
    assert definition.runtime_snapshot()["model"] == "gpt-4.1"


@pytest.mark.asyncio
async def test_an_agent_from_another_tenant_is_not_found(tenant_id) -> None:
    agent_id = uuid4()
    resolver = _resolver(
        tenant_id, agent=SimpleNamespace(agent_id=agent_id, tenant_id=uuid4(), name="x")
    )

    with pytest.raises(NotFoundServiceException, match="agent_not_found"):
        await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)


@pytest.mark.asyncio
async def test_an_agent_without_an_active_version_cannot_run(tenant_id) -> None:
    agent_id = uuid4()
    resolver = _resolver(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="x"),
        active_version_id=None,
    )

    with pytest.raises(ResourceBlockedServiceException, match="agent_version_not_active"):
        await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)


@pytest.mark.asyncio
async def test_an_unpublished_version_is_blocked(tenant_id) -> None:
    agent_id = uuid4()
    version = _agent_version(agent_id=agent_id, status=VersionStatus.DRAFT.value)
    resolver = _resolver(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="x"),
        active_version_id=version.agent_version_id,
        agent_version=version,
    )

    with pytest.raises(ResourceBlockedServiceException, match="agent_version_blocked"):
        await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)


@pytest.mark.asyncio
async def test_a_version_without_an_ai_policy_cannot_run(tenant_id) -> None:
    agent_id = uuid4()
    version = _agent_version(agent_id=agent_id, ai_execution_policy_version_id=None)
    resolver = _resolver(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="x"),
        active_version_id=version.agent_version_id,
        agent_version=version,
    )

    with pytest.raises(ResourceBlockedServiceException, match="ai_execution_policy_not_active"):
        await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)


@pytest.mark.asyncio
async def test_a_tenant_without_an_active_billing_policy_cannot_run(tenant_id) -> None:
    agent_id = uuid4()
    version = _agent_version(agent_id=agent_id)
    resolver = _resolver(
        tenant_id,
        agent=SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id, name="x"),
        active_version_id=version.agent_version_id,
        agent_version=version,
        policy_version=SimpleNamespace(status=VersionStatus.PUBLISHED.value, model_id=uuid4()),
        model=SimpleNamespace(name="gpt-4.1"),
        billing_policy_version_id=None,
    )

    with pytest.raises(ResourceBlockedServiceException, match="billing_policy_not_active"):
        await resolver.resolve(tenant_id=tenant_id, agent_id=agent_id)


def test_function_names_stay_safe_and_bounded() -> None:
    tool_config_id = uuid4()

    assert normalize_tool_function_name("search flights", tool_config_id) == "search_flights"
    assert normalize_tool_function_name("", tool_config_id).startswith("tool_")
    assert len(normalize_tool_function_name("x" * 200, tool_config_id)) == 64


def test_a_missing_request_schema_falls_back_to_an_open_object() -> None:
    assert tool_request_schema({}) == {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }
    assert tool_request_schema({"request_schema": {"properties": {"a": {}}}})["type"] == "object"
    typed = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert tool_request_schema({"request_schema": typed}) == typed


@pytest.mark.asyncio
async def test_the_catalog_is_the_agent_versions_published_tools(tenant_id) -> None:
    tool_config_id = uuid4()
    tools_repository = MagicMock()
    tools_repository.list_tool_bindings_by_agent_version_id = AsyncMock(
        return_value=[SimpleNamespace(tool_config_id=tool_config_id)]
    )
    tools_repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock(
        return_value=[
            (
                SimpleNamespace(
                    tool_config_id=tool_config_id,
                    tool_id=uuid4(),
                    config={"summary": "finds flights", "request_schema": {"type": "object"}},
                ),
                SimpleNamespace(name="search"),
            )
        ]
    )

    catalog = await AgentToolCatalog(tools_repository).list_agent_version_tools(
        tenant_id=tenant_id, agent_version_id=uuid4()
    )

    assert [tool.function_name for tool in catalog] == ["search"]
    assert catalog[0].description == "finds flights"


@pytest.mark.asyncio
async def test_duplicate_tool_names_are_disambiguated(tenant_id) -> None:
    first_id, second_id = uuid4(), uuid4()
    tools_repository = MagicMock()
    tools_repository.list_tool_bindings_by_agent_version_id = AsyncMock(
        return_value=[
            SimpleNamespace(tool_config_id=first_id),
            SimpleNamespace(tool_config_id=second_id),
        ]
    )
    tools_repository.list_published_tool_configs_with_tools_by_config_ids = AsyncMock(
        return_value=[
            (
                SimpleNamespace(tool_config_id=first_id, tool_id=uuid4(), config={}),
                SimpleNamespace(name="search"),
            ),
            (
                SimpleNamespace(tool_config_id=second_id, tool_id=uuid4(), config={}),
                SimpleNamespace(name="search"),
            ),
        ]
    )

    catalog = await AgentToolCatalog(tools_repository).list_agent_version_tools(
        tenant_id=tenant_id, agent_version_id=uuid4()
    )

    names = [tool.function_name for tool in catalog]
    assert names[0] == "search"
    assert names[1].startswith("search_")
    assert len(set(names)) == 2


@pytest.mark.asyncio
async def test_an_agent_version_with_no_bindings_has_no_tools(tenant_id) -> None:
    tools_repository = MagicMock()
    tools_repository.list_tool_bindings_by_agent_version_id = AsyncMock(return_value=[])

    catalog = await AgentToolCatalog(tools_repository).list_agent_version_tools(
        tenant_id=tenant_id, agent_version_id=uuid4()
    )

    assert catalog == []
