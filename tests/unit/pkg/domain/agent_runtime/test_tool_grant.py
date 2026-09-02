"""Execution-scoped tool authorization.

An agent version may be bound to many tools; a run may be granted a subset. These tests pin the
rule that the subset is what the runtime enforces, not the agent's wider catalogue.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from domain.execution.schemas.agent_run import AgentRunToolGrant
from domain.execution.services.agent_runtime.tool_grant import ToolGrantResolver
from exceptions.service_exceptions import DomainValidationException
from tests.unit.pkg.domain.agent_runtime.conftest import (
    agents_repository_for,
    build_definition,
    build_tool,
)


@pytest.mark.asyncio
async def test_omitted_allow_list_grants_every_tool_bound_to_the_version(tenant_id) -> None:
    definition = build_definition([build_tool("search"), build_tool("book")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    grant = await resolver.resolve(
        tenant_id=tenant_id, definition=definition, requested=AgentRunToolGrant()
    )

    assert {tool.function_name for tool in grant.tools} == {"search", "book"}


@pytest.mark.asyncio
async def test_allow_list_narrows_the_run_to_the_named_subset(tenant_id) -> None:
    definition = build_definition([build_tool("search"), build_tool("book")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    grant = await resolver.resolve(
        tenant_id=tenant_id,
        definition=definition,
        requested=AgentRunToolGrant(allowed_tool_names=["search"]),
    )

    assert [tool.function_name for tool in grant.tools] == ["search"]
    assert grant.binding_for("book") is None


@pytest.mark.asyncio
async def test_empty_allow_list_grants_no_tool_at_all(tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    grant = await resolver.resolve(
        tenant_id=tenant_id,
        definition=definition,
        requested=AgentRunToolGrant(allowed_tool_names=[]),
    )

    assert grant.tools == []


@pytest.mark.asyncio
async def test_requesting_a_tool_the_agent_is_not_bound_to_is_rejected(tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    with pytest.raises(DomainValidationException, match="tool_not_bound_to_agent_version"):
        await resolver.resolve(
            tenant_id=tenant_id,
            definition=definition,
            requested=AgentRunToolGrant(allowed_tool_names=["wire_transfer"]),
        )


@pytest.mark.asyncio
async def test_delegation_target_must_belong_to_the_caller_tenant(tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    foreign_agent_id = uuid4()
    resolver = ToolGrantResolver(
        agents_repository=agents_repository_for(tenant_id, known_agent_ids=set())
    )

    with pytest.raises(DomainValidationException, match="delegate_agent_not_found"):
        await resolver.resolve(
            tenant_id=tenant_id,
            definition=definition,
            requested=AgentRunToolGrant(
                allow_agent_delegation=True, delegate_agent_ids=[foreign_agent_id]
            ),
        )


@pytest.mark.asyncio
async def test_an_agent_may_not_delegate_to_itself(tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    with pytest.raises(DomainValidationException, match="agent_cannot_delegate_to_itself"):
        await resolver.resolve(
            tenant_id=tenant_id,
            definition=definition,
            requested=AgentRunToolGrant(
                allow_agent_delegation=True, delegate_agent_ids=[definition.agent_id]
            ),
        )


def test_delegation_without_a_target_is_a_contract_error() -> None:
    with pytest.raises(ValueError, match="delegate_agent_ids_required_when_delegation_allowed"):
        AgentRunToolGrant(allow_agent_delegation=True)


@pytest.mark.asyncio
async def test_snapshot_records_exactly_what_the_run_may_call(tenant_id) -> None:
    definition = build_definition([build_tool("search"), build_tool("book")])
    resolver = ToolGrantResolver(agents_repository=agents_repository_for(tenant_id))

    grant = await resolver.resolve(
        tenant_id=tenant_id,
        definition=definition,
        requested=AgentRunToolGrant(allowed_tool_names=["search"]),
    )
    snapshot = grant.snapshot()

    assert [tool["function_name"] for tool in snapshot["tools"]] == ["search"]
    assert snapshot["allow_agent_delegation"] is False
    assert snapshot["delegation_tool_name"] is None
