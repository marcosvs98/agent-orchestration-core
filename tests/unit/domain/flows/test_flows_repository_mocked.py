"""FlowsRepository paths with mocked AsyncSession (no DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.flows.repositories.flows_repository import FlowsRepository


def _session_cm(session: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def flows_repo() -> FlowsRepository:
    db = MagicMock()
    return FlowsRepository(db)


@pytest.mark.asyncio
async def test_get_flow(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_flow(uuid4()) is row


@pytest.mark.asyncio
async def test_get_flow_version(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_flow_version(uuid4()) is row


@pytest.mark.asyncio
async def test_get_node(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_node(uuid4()) is row


@pytest.mark.asyncio
async def test_get_router(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_router(uuid4()) is row


@pytest.mark.asyncio
async def test_get_flow_graph_by_flow_version(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_flow_graph_by_flow_version(uuid4()) is row


@pytest.mark.asyncio
async def test_get_active_flow_version_id(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    vid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_active_flow_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_list_flows(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    f1, f2 = MagicMock(), MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [f1, f2]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.list_flows(tenant_id=uuid4()) == [f1, f2]


@pytest.mark.asyncio
async def test_list_flow_versions(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    v1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [v1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.list_flow_versions(flow_id=uuid4()) == [v1]


@pytest.mark.asyncio
async def test_list_nodes_for_flow_version(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    n1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [n1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.list_nodes_for_flow_version(uuid4()) == [n1]


@pytest.mark.asyncio
async def test_list_routing_rules_for_flow_version(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    r1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [r1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.list_routing_rules_for_flow_version(uuid4()) == [r1]


@pytest.mark.asyncio
async def test_get_active_prompt_id_by_node_type(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    pid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=pid)
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await flows_repo.get_active_prompt_id_by_node_type("llm") == pid


@pytest.mark.asyncio
async def test_list_active_system_node_templates(flows_repo: FlowsRepository) -> None:
    session = AsyncMock()
    t1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [t1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    flows_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await flows_repo.list_active_system_node_templates()
    assert out == [t1]
