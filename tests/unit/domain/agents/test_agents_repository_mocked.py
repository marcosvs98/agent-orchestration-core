"""AgentsRepository paths with mocked session + tracer."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from adapters.cache.redis_adapter import RedisAdapter
from domain.agents.repositories.agents_repository import AgentsRepository


def _tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


def _session_cm(session: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def agents_repo() -> AgentsRepository:
    db = MagicMock()
    cache = MagicMock(spec=RedisAdapter)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return AgentsRepository(db, tracer=_tracer(), cache_adapter=cache)


@pytest.mark.asyncio
async def test_get_agent(agents_repo: AgentsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await agents_repo.get_agent(uuid4()) is row


@pytest.mark.asyncio
async def test_get_agent_version_miss_then_cache(
    agents_repo: AgentsRepository,
) -> None:
    ver = MagicMock()
    ver.to_dict.return_value = {"id": "x"}
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=ver)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await agents_repo.get_agent_version(uuid4())
    assert out is ver
    agents_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_active_agent_version_id(agents_repo: AgentsRepository) -> None:
    session = AsyncMock()
    vid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await agents_repo.get_active_agent_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_list_agents(agents_repo: AgentsRepository) -> None:
    session = AsyncMock()
    a1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [a1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await agents_repo.list_agents(tenant_id=uuid4()) == [a1]


@pytest.mark.asyncio
async def test_count_active_agent_versions(agents_repo: AgentsRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar = MagicMock(return_value=4)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await agents_repo.count_active_agent_versions(uuid4()) == 4


@pytest.mark.asyncio
async def test_get_agent_version_id_by_node_id(agents_repo: AgentsRepository) -> None:
    session = AsyncMock()
    binding = MagicMock()
    binding.agent_version_id = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=binding)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await agents_repo.get_agent_version_id_by_node_id(uuid4())
    assert out == binding.agent_version_id


@pytest.mark.asyncio
async def test_resolve_effective_rag_config_id_from_node_column(
    agents_repo: AgentsRepository,
) -> None:
    session = AsyncMock()
    rid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=rid)
    session.execute = AsyncMock(return_value=res)
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await agents_repo.resolve_effective_rag_config_id_for_node(uuid4()) == rid


@pytest.mark.asyncio
async def test_list_node_bindings_by_agent_version_id(
    agents_repo: AgentsRepository,
) -> None:
    session = AsyncMock()
    b1 = MagicMock()
    r1 = MagicMock()
    r1.scalar_one_or_none.return_value = uuid4()
    r2 = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [b1]
    r2.scalars.return_value = scalars
    session.execute = AsyncMock(side_effect=[r1, r2])
    agents_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    tid, avid = uuid4(), uuid4()
    out = await agents_repo.list_node_bindings_by_agent_version_id(
        tenant_id=tid, agent_version_id=avid
    )
    assert out == [b1]
