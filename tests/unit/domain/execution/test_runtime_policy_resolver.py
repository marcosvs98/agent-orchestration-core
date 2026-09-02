"""Behavioural tests for RuntimePolicyResolver (precedence FLOW → TENANT → DEFAULT)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.runtime_policy_resolver import RuntimePolicyResolver
from domain.governance.repositories.runtime_policy_repository import (
    RuntimePolicyRepository,
)
from domain.governance.schemas.runtime_policy import (
    ResolvedRuntimePolicy,
    RuntimePolicySource,
)


def _tracer() -> MagicMock:
    t = MagicMock(spec=RuntimeTracerPort)
    h = MagicMock()
    h.success = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(h)
    return t


@pytest.mark.asyncio
async def test_resolve_flow_policy_when_active() -> None:
    tid, fid = uuid4(), uuid4()
    repo = MagicMock(spec=RuntimePolicyRepository)
    row = MagicMock()
    row.runtime_policy_id = uuid4()
    row.version = "2"
    row.policy_definition = {}
    repo.get_active_flow_policy = AsyncMock(return_value=row)
    repo.get_active_tenant_policy = AsyncMock(return_value=None)

    resolver = RuntimePolicyResolver(
        repository=repo,
        default_policy={"version": "1", "policy_definition": {}},
        tracer=_tracer(),
    )
    out = await resolver.resolve(tenant_id=tid, flow_id=fid)
    assert isinstance(out, ResolvedRuntimePolicy)
    assert out.source == RuntimePolicySource.FLOW
    assert out.flow_id == fid
    repo.get_active_flow_policy.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_tenant_policy_when_no_flow_id() -> None:
    tid = uuid4()
    repo = MagicMock(spec=RuntimePolicyRepository)
    row = MagicMock()
    row.runtime_policy_id = uuid4()
    row.version = "3"
    row.policy_definition = {}
    row.flow_id = None
    repo.get_active_tenant_policy = AsyncMock(return_value=row)

    resolver = RuntimePolicyResolver(
        repository=repo,
        default_policy={"version": "1", "policy_definition": {}},
        tracer=_tracer(),
    )
    out = await resolver.resolve(tenant_id=tid, flow_id=None)
    assert out.source == RuntimePolicySource.TENANT


@pytest.mark.asyncio
async def test_resolve_falls_back_to_tenant_when_flow_policy_missing() -> None:
    tid, fid = uuid4(), uuid4()
    repo = MagicMock(spec=RuntimePolicyRepository)
    row = MagicMock()
    row.runtime_policy_id = uuid4()
    row.version = "4"
    row.policy_definition = {}
    row.flow_id = None
    repo.get_active_flow_policy = AsyncMock(return_value=None)
    repo.get_active_tenant_policy = AsyncMock(return_value=row)

    resolver = RuntimePolicyResolver(
        repository=repo,
        default_policy={"version": "1", "policy_definition": {}},
        tracer=_tracer(),
    )
    out = await resolver.resolve(tenant_id=tid, flow_id=fid)
    assert out.source == RuntimePolicySource.TENANT
    assert out.version == "4"
    repo.get_active_tenant_policy.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_default_when_flow_and_tenant_missing() -> None:
    tid, fid = uuid4(), uuid4()
    repo = MagicMock(spec=RuntimePolicyRepository)
    repo.get_active_flow_policy = AsyncMock(return_value=None)
    repo.get_active_tenant_policy = AsyncMock(return_value=None)

    resolver = RuntimePolicyResolver(
        repository=repo,
        default_policy={"version": "7", "policy_definition": {}},
        tracer=_tracer(),
    )
    out = await resolver.resolve(tenant_id=tid, flow_id=fid)
    assert out.source == RuntimePolicySource.DEFAULT
    assert out.version == "7"


@pytest.mark.asyncio
async def test_resolve_default_when_no_flow_and_no_tenant() -> None:
    tid = uuid4()
    repo = MagicMock(spec=RuntimePolicyRepository)
    repo.get_active_tenant_policy = AsyncMock(return_value=None)

    resolver = RuntimePolicyResolver(
        repository=repo,
        default_policy={"version": "9", "policy_definition": {}},
        tracer=_tracer(),
    )
    out = await resolver.resolve(tenant_id=tid, flow_id=None)
    assert out.source == RuntimePolicySource.DEFAULT
    assert out.version == "9"
