"""Targeted ExecutionRepository paths with AsyncMock sessions (raises coverage without DB)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.repositories.execution_repository import ExecutionRepository


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
def exec_repo() -> ExecutionRepository:
    db = MagicMock()
    cache = MagicMock(spec=RedisAdapter)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return ExecutionRepository(db, _tracer(), cache)


@pytest.mark.asyncio
async def test_merge_flow_run_runtime_contract_no_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.merge_flow_run_runtime_contract(flow_run_id=uuid4(), patch={"k": "v"})
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_merge_flow_run_runtime_contract_updates(exec_repo: ExecutionRepository) -> None:
    row = MagicMock()
    row.runtime_contract = {}
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    fid = uuid4()
    await exec_repo.merge_flow_run_runtime_contract(flow_run_id=fid, patch={"a": 1})
    session.commit.assert_awaited_once()
    assert row.runtime_contract == {"a": 1}


@pytest.mark.asyncio
async def test_flush_execution_events_empty_buffer(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(AsyncMock()))
    await exec_repo.flush_execution_events(fid)


@pytest.mark.asyncio
async def test_start_event_batching_registers_buffer(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    exec_repo.start_event_batching(fid)
    assert fid in exec_repo._batching_flow_runs


@pytest.mark.asyncio
async def test_get_flow_run_returns_model(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    fid = uuid4()
    out = await exec_repo.get_flow_run(fid)
    assert out is row


@pytest.mark.asyncio
async def test_get_flow_run_returns_none(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_run(uuid4()) is None


@pytest.mark.asyncio
async def test_get_interaction_metadata_empty_when_no_flow_run(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.get_flow_run = AsyncMock(return_value=None)
    assert await exec_repo.get_interaction_metadata_for_flow_run(uuid4()) == {}


@pytest.mark.asyncio
async def test_get_interaction_metadata_empty_when_no_interaction_id(
    exec_repo: ExecutionRepository,
) -> None:
    fr = MagicMock()
    fr.interaction_id = None
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    assert await exec_repo.get_interaction_metadata_for_flow_run(uuid4()) == {}


@pytest.mark.asyncio
async def test_get_tool_run_returns_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_tool_run(uuid4()) is row


@pytest.mark.asyncio
async def test_get_node_run_returns_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_node_run(uuid4()) is row


@pytest.mark.asyncio
async def test_get_graph_state_returns_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_graph_state(uuid4()) is row


@pytest.mark.asyncio
async def test_count_tool_runs_for_flow_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one = MagicMock(return_value=3)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.count_tool_runs_for_flow_run(uuid4()) == 3


@pytest.mark.asyncio
async def test_count_agent_runs_for_flow_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one = MagicMock(return_value=7)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.count_agent_runs_for_flow_run(uuid4()) == 7


@pytest.mark.asyncio
async def test_get_session_returns_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_session(uuid4()) is row


@pytest.mark.asyncio
async def test_get_user_memory_profile_empty(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_user_memory_profile(tenant_id=uuid4(), user_id="u") == {}


@pytest.mark.asyncio
async def test_get_user_memory_profile_from_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {"profile_schema_version": 1, "memory_preferences": {"a": {"value": 1}}}
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_user_memory_profile(tenant_id=uuid4(), user_id="u")
    assert out == row.profile


@pytest.mark.asyncio
async def test_get_user_preferences(exec_repo: ExecutionRepository) -> None:
    exec_repo.get_user_memory_profile = AsyncMock(
        return_value={
            "profile_schema_version": 1,
            "memory_preferences": {"x": {"value": 2}},
        }
    )
    prefs = await exec_repo.get_user_preferences(tenant_id=uuid4(), user_id="u")
    assert prefs["x"] == 2


@pytest.mark.asyncio
async def test_get_flow_context(exec_repo: ExecutionRepository) -> None:
    sid, tid = uuid4(), uuid4()
    fr = MagicMock()
    fr.session_id = sid
    sess = MagicMock()
    sess.tenant_id = tid
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    exec_repo.get_session = AsyncMock(return_value=sess)
    assert await exec_repo.get_flow_context(uuid4()) == (sid, tid)


@pytest.mark.asyncio
async def test_get_interaction_metadata_returns_dict(exec_repo: ExecutionRepository) -> None:
    iid = uuid4()
    fr = MagicMock()
    fr.interaction_id = iid
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value={"meta": True})
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_interaction_metadata_for_flow_run(uuid4())
    assert out == {"meta": True}


@pytest.mark.asyncio
async def test_get_latest_waiting_flow_run_id(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    u1, u2 = uuid4(), uuid4()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [u1, u2]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    origin, cands = await exec_repo.get_latest_waiting_flow_run_id(
        session_id=uuid4(),
        correlation_id=uuid4(),
        flow_version_id=uuid4(),
        user_id="u",
    )
    assert origin == u1
    assert cands == [u1, u2]


@pytest.mark.asyncio
async def test_get_active_billing_policy_version_id_sets_cache(
    exec_repo: ExecutionRepository,
) -> None:
    vid = uuid4()
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_active_billing_policy_version_id(uuid4())
    assert out == vid
    exec_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_billing_policy_version_from_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    pid = uuid4()
    policy = MagicMock()
    policy.to_dict.return_value = {"id": str(pid)}
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=policy)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_billing_policy_version(pid)
    assert out is policy
    exec_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_active_memory_policy_version_id_sets_cache(
    exec_repo: ExecutionRepository,
) -> None:
    vid = uuid4()
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_memory_policy_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_get_memory_policy_version_from_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    pid = uuid4()
    policy = MagicMock()
    policy.to_dict.return_value = {"id": str(pid)}
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=policy)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_memory_policy_version(pid)
    assert out is policy


@pytest.mark.asyncio
async def test_get_active_rag_policy_version_id_sets_cache(
    exec_repo: ExecutionRepository,
) -> None:
    vid = uuid4()
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_rag_policy_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_get_rag_policy_version_from_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    pid = uuid4()
    policy = MagicMock()
    policy.to_dict.return_value = {"id": str(pid)}
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=policy)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_rag_policy_version(pid)
    assert out is policy


@pytest.mark.asyncio
async def test_get_flow_version(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_version(uuid4()) is row


@pytest.mark.asyncio
async def test_get_flow(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow(uuid4()) is row


@pytest.mark.asyncio
async def test_get_active_flow_version_id(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    vid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_flow_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_get_tool_config(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_tool_config(uuid4()) is row


@pytest.mark.asyncio
async def test_get_agent_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_agent_run(uuid4()) is row


@pytest.mark.asyncio
async def test_get_node(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_node(uuid4()) is row


@pytest.mark.asyncio
async def test_get_model(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_model(uuid4()) is row


@pytest.mark.asyncio
async def test_list_node_runs(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    n1, n2 = MagicMock(), MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [n1, n2]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.list_node_runs(tenant_id=uuid4())
    assert out == [n1, n2]


@pytest.mark.asyncio
async def test_list_agent_runs(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    a1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [a1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.list_agent_runs(tenant_id=uuid4(), flow_run_id=uuid4())
    assert out == [a1]
