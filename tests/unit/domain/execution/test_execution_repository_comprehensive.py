"""Heavy mocked coverage for ExecutionRepository (no real DB).

Keeps the global --cov-fail-under gate honest once execution_repository is measured.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import FlowRunInput
from domain.execution.services.state_machine import ToolRunStatus
from exceptions.service_exceptions import (
    DomainConflictException,
    DomainValidationException,
    NotFoundServiceException,
)
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
    cache.delete = AsyncMock()
    return ExecutionRepository(db, _tracer(), cache)


# --- _persist_execution_events_batch & batching ---


@pytest.mark.asyncio
async def test_persist_execution_events_batch_writes(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    uid = "user-1"
    eid = uuid4()
    events = [
        {
            "event_id": eid,
            "tenant_id": uuid4(),
            "user_id": uid,
            "session_id": uuid4(),
            "correlation_id": uuid4(),
            "event_type": "TEST",
            "payload": {"k": 1},
        }
    ]
    session = AsyncMock()
    seq_res = MagicMock()
    seq_res.scalar_one = MagicMock(return_value=0)
    session.execute = AsyncMock(side_effect=[MagicMock(), seq_res])
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo._persist_execution_events_batch(fid, events)
    assert session.add.called
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_batch_resolves_user_from_flow_run(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    eid = uuid4()
    events = [
        {
            "event_id": eid,
            "tenant_id": uuid4(),
            "user_id": None,
            "session_id": uuid4(),
            "correlation_id": uuid4(),
            "event_type": "TEST",
            "payload": {},
        }
    ]
    session = AsyncMock()
    uid_res = MagicMock()
    uid_res.scalar_one_or_none = MagicMock(return_value="resolved-user")
    seq_res = MagicMock()
    seq_res.scalar_one = MagicMock(return_value=0)
    session.execute = AsyncMock(side_effect=[uid_res, MagicMock(), seq_res])
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo._persist_execution_events_batch(fid, events)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_batch_raises_when_no_user(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    eid = uuid4()
    events = [
        {
            "event_id": eid,
            "tenant_id": uuid4(),
            "user_id": None,
            "session_id": uuid4(),
            "correlation_id": uuid4(),
            "event_type": "T",
            "payload": {},
        }
    ]
    session = AsyncMock()
    uid_res = MagicMock()
    uid_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=uid_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="flow_run_user_not_found"):
        await exec_repo._persist_execution_events_batch(fid, events)


@pytest.mark.asyncio
async def test_end_event_batching_flushes(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    exec_repo._persist_execution_events_batch = AsyncMock()
    await exec_repo.end_event_batching(fid)
    exec_repo._persist_execution_events_batch.assert_awaited_once_with(fid, [])


@pytest.mark.asyncio
async def test_append_event_batching_flushes_when_full(exec_repo: ExecutionRepository) -> None:
    exec_repo._event_batch_size = 1
    exec_repo._persist_execution_events_batch = AsyncMock()
    fid = uuid4()
    exec_repo.start_event_batching(fid)
    await exec_repo.append_execution_event(
        tenant_id=uuid4(),
        user_id="u",
        session_id=uuid4(),
        flow_run_id=fid,
        event_type="E",
        payload={},
        correlation_id=uuid4(),
    )
    exec_repo._persist_execution_events_batch.assert_awaited()


@pytest.mark.asyncio
async def test_append_event_immediate_path(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    session = AsyncMock()
    uid_res = MagicMock()
    uid_res.scalar_one_or_none = MagicMock(return_value="u")
    seq_res = MagicMock()
    seq_res.scalar_one = MagicMock(return_value=0)
    session.execute = AsyncMock(side_effect=[uid_res, MagicMock(), seq_res])
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    eid = await exec_repo.append_execution_event(
        tenant_id=uuid4(),
        user_id=None,
        session_id=uuid4(),
        flow_run_id=fid,
        event_type="E",
        payload={},
        correlation_id=uuid4(),
    )
    assert eid is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_append_event_raises_when_no_user(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    session = AsyncMock()
    uid_res = MagicMock()
    uid_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=uid_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="flow_run_user_not_found"):
        await exec_repo.append_execution_event(
            tenant_id=uuid4(),
            user_id=None,
            session_id=uuid4(),
            flow_run_id=fid,
            event_type="E",
            payload={},
            correlation_id=uuid4(),
        )


# --- create_flow_run & flow mutations ---


@pytest.mark.asyncio
async def test_create_flow_run_commits(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    inp = FlowRunInput(user_input="hi")
    rid = await exec_repo.create_flow_run(
        session_id=uuid4(),
        flow_version_id=uuid4(),
        correlation_id=uuid4(),
        origin_flow_run_id=None,
        user_id="u",
        input_payload=inp,
    )
    assert rid is not None
    assert session.add.call_count == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_active_flow_deployment(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_flow_deployment(flow_id=uuid4()) is row


@pytest.mark.asyncio
async def test_get_flow_snapshot_by_id(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_snapshot_by_id(uuid4()) is row


@pytest.mark.asyncio
async def test_get_flow_snapshot_by_flow_version(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_snapshot_by_flow_version(uuid4()) is row


@pytest.mark.asyncio
async def test_set_root_observation_id(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.set_root_observation_id(
        flow_run_id=uuid4(), root_observation_id="obs"
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_flow_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.complete_flow_run(
        flow_run_id=uuid4(), status="DONE", output={"a": 1}
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_flow_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.fail_flow_run(
        flow_run_id=uuid4(), failure_reason="x", error={"e": 1}
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_flow_run_default_error(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.fail_flow_run(flow_run_id=uuid4(), failure_reason="x", error=None)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_flow_run_status(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.set_flow_run_status(
        flow_run_id=uuid4(), status="RUNNING", canonical_status="RUNNING"
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_flow_run_output(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.set_flow_run_output(flow_run_id=uuid4(), output={})
    session.commit.assert_awaited_once()


# --- create_session ---


@pytest.mark.asyncio
async def test_create_session_new_user_and_session(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    ures = MagicMock()
    ures.scalar_one_or_none = MagicMock(return_value=None)
    sres = MagicMock()
    sres.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(side_effect=[ures, sres])
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.create_session(
        session_id=uuid4(), tenant_id=uuid4(), user_id="u1"
    )
    assert session.add.call_count >= 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_session_conflict(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    ures = MagicMock()
    ures.scalar_one_or_none = MagicMock(return_value=MagicMock())
    existing = MagicMock()
    existing.tenant_id = uuid4()
    existing.user_id = "other"
    sres = MagicMock()
    sres.scalar_one_or_none = MagicMock(return_value=existing)
    session.execute = AsyncMock(side_effect=[ures, sres])
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(DomainConflictException, match="session_user_mismatch"):
        await exec_repo.create_session(
            session_id=uuid4(), tenant_id=uuid4(), user_id="u1"
        )


@pytest.mark.asyncio
async def test_create_session_existing_match(exec_repo: ExecutionRepository) -> None:
    tid = uuid4()
    session = AsyncMock()
    ures = MagicMock()
    ures.scalar_one_or_none = MagicMock(return_value=MagicMock())
    existing = MagicMock()
    existing.tenant_id = tid
    existing.user_id = "u1"
    sres = MagicMock()
    sres.scalar_one_or_none = MagicMock(return_value=existing)
    session.execute = AsyncMock(side_effect=[ures, sres])
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.create_session(session_id=uuid4(), tenant_id=tid, user_id="u1")
    session.commit.assert_awaited_once()


# --- get_flow_context errors ---


@pytest.mark.asyncio
async def test_get_flow_context_missing_flow_run(exec_repo: ExecutionRepository) -> None:
    exec_repo.get_flow_run = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
        await exec_repo.get_flow_context(uuid4())


@pytest.mark.asyncio
async def test_get_flow_context_missing_session(exec_repo: ExecutionRepository) -> None:
    fr = MagicMock()
    fr.session_id = uuid4()
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    exec_repo.get_session = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="session_not_found"):
        await exec_repo.get_flow_context(uuid4())


# --- preferences & profile ---


@pytest.mark.asyncio
async def test_get_user_memory_preferences_and_profile(exec_repo: ExecutionRepository) -> None:
    exec_repo.get_user_memory_profile = AsyncMock(
        return_value={"profile_schema_version": 1, "memory_preferences": {}}
    )
    prefs, prof = await exec_repo.get_user_memory_preferences_and_profile(
        tenant_id=uuid4(), user_id="u"
    )
    assert prefs == {}
    assert prof["profile_schema_version"] == 1


@pytest.mark.asyncio
async def test_upsert_user_preference_delegates(exec_repo: ExecutionRepository) -> None:
    exec_repo.upsert_user_preference_deterministic = AsyncMock(
        return_value=MagicMock(version=3)
    )
    v = await exec_repo.upsert_user_preference(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value=1,
        source="s",
    )
    assert v == 3


@pytest.mark.asyncio
async def test_upsert_user_preference_insert_new_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=lock_res)
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value="v",
        source="src",
        source_priority_map={"src": 10},
        ignore_if_unchanged=False,
    )
    assert out.updated is True
    assert out.reason == "inserted"


@pytest.mark.asyncio
async def test_upsert_user_preference_unchanged(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {
        "profile_schema_version": 1,
        "memory_preferences": {"k": {"value": 1, "source": "s", "version": 1}},
    }
    row.profile_version = 1
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=lock_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value=1,
        source="s",
        source_priority_map={"s": 10},
        ignore_if_unchanged=True,
    )
    assert out.updated is False
    assert out.reason == "unchanged"


@pytest.mark.asyncio
async def test_upsert_user_preference_priority_denied(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {
        "profile_schema_version": 1,
        "memory_preferences": {
            "k": {"value": 2, "source": "high", "version": 1},
        },
    }
    row.profile_version = 2
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=lock_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value=9,
        source="low",
        source_priority_map={"high": 100, "low": 1},
        ignore_if_unchanged=False,
    )
    assert out.updated is False
    assert out.reason == "source_priority_denied"


@pytest.mark.asyncio
async def test_upsert_user_preference_update(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {
        "profile_schema_version": 1,
        "memory_preferences": {
            "k": {"value": 2, "source": "low", "version": 2},
        },
    }
    row.profile_version = 2
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=lock_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value=3,
        source="high",
        source_priority_map={"high": 10, "low": 1},
        ignore_if_unchanged=False,
    )
    assert out.updated is True
    assert out.reason == "updated"


@pytest.mark.asyncio
async def test_upsert_user_memory_profile(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one = MagicMock(return_value=2)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    v = await exec_repo.upsert_user_memory_profile(
        tenant_id=uuid4(), user_id="u", profile={"profile_schema_version": 1}
    )
    assert v == 2


@pytest.mark.asyncio
async def test_next_event_sequence(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    seq_res = MagicMock()
    seq_res.scalar_one = MagicMock(return_value=4)
    session.execute = AsyncMock(side_effect=[MagicMock(), seq_res])
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.next_event_sequence(uuid4()) == 5


# --- interactions ---


@pytest.mark.asyncio
async def test_create_interaction(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    iid = await exec_repo.create_interaction(
        session_id=uuid4(),
        channel="http",
        payload={},
        headers={},
        metadata={},
        external_message_id=None,
        request_id=None,
        trace_id=None,
    )
    assert iid is not None


@pytest.mark.asyncio
async def test_link_interaction_to_flow_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(side_effect=[res, AsyncMock()])
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.link_interaction_to_flow_run(
        interaction_id=uuid4(), flow_run_id=uuid4()
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_interaction_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="interaction_not_found"):
        await exec_repo.link_interaction_to_flow_run(
            interaction_id=uuid4(), flow_run_id=uuid4()
        )


@pytest.mark.asyncio
async def test_set_current_interaction_result(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.set_current_interaction_result_for_flow_run(
        flow_run_id=uuid4(), output={"x": 1}, result_node_run_id=uuid4()
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_interaction_metadata_non_dict_raw(exec_repo: ExecutionRepository) -> None:
    fr = MagicMock()
    fr.interaction_id = uuid4()
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value="not-a-dict")
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_interaction_metadata_for_flow_run(uuid4()) == {}


# --- list & stamps ---


@pytest.mark.asyncio
async def test_list_execution_events(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    ev = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [ev]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.list_execution_events(
        flow_run_id=uuid4(), correlation_id=uuid4(), limit=10
    )
    assert out == [ev]


@pytest.mark.asyncio
async def test_stamp_agent_run_billing(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    ar = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=ar)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.stamp_agent_run_billing_policy(
        agent_run_id=uuid4(), billing_policy_version_id=uuid4()
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stamp_agent_run_billing_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await exec_repo.stamp_agent_run_billing_policy(
            agent_run_id=uuid4(), billing_policy_version_id=uuid4()
        )


@pytest.mark.asyncio
async def test_stamp_tool_run_billing(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    tr = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=tr)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.stamp_tool_run_billing_policy(
        tool_run_id=uuid4(),
        billing_policy_version_id=uuid4(),
        estimated_cost=1.5,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stamp_tool_run_billing_no_estimated_cost(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    tr = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=tr)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.stamp_tool_run_billing_policy(
        tool_run_id=uuid4(), billing_policy_version_id=uuid4(), estimated_cost=None
    )
    session.commit.assert_awaited_once()


# --- tool / node / agent updates ---


@pytest.mark.asyncio
async def test_update_tool_run_result_success_finished(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.update_tool_run_result(
        tool_run_id=uuid4(),
        status=ToolRunStatus.SUCCESS,
        canonical_status="SUCCESS",
        output={},
        error=None,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_tool_run_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="tool_run_not_found"):
        await exec_repo.update_tool_run_result(
            tool_run_id=uuid4(),
            status="X",
            canonical_status="X",
            output=None,
            error=None,
        )


@pytest.mark.asyncio
async def test_get_flow_run_id_via_node_run(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = uuid4()
    tr.agent_run_id = None
    nr = MagicMock()
    nr.flow_run_id = uuid4()
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    exec_repo.get_node_run = AsyncMock(return_value=nr)
    assert await exec_repo.get_flow_run_id_for_tool_run(uuid4()) == nr.flow_run_id


@pytest.mark.asyncio
async def test_get_flow_run_id_via_agent_run(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = None
    tr.agent_run_id = uuid4()
    ar = MagicMock()
    ar.node_run_id = uuid4()
    nr = MagicMock()
    nr.flow_run_id = uuid4()
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    exec_repo.get_agent_run = AsyncMock(return_value=ar)
    exec_repo.get_node_run = AsyncMock(return_value=nr)
    assert await exec_repo.get_flow_run_id_for_tool_run(uuid4()) == nr.flow_run_id


@pytest.mark.asyncio
async def test_get_flow_run_id_tool_missing_parent(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = None
    tr.agent_run_id = None
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    with pytest.raises(DomainValidationException, match="tool_run_missing_parent"):
        await exec_repo.get_flow_run_id_for_tool_run(uuid4())


@pytest.mark.asyncio
async def test_get_flow_run_id_tool_not_found(exec_repo: ExecutionRepository) -> None:
    exec_repo.get_tool_run = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="tool_run_not_found"):
        await exec_repo.get_flow_run_id_for_tool_run(uuid4())


@pytest.mark.asyncio
async def test_create_run_failure_for_tool_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    rid = await exec_repo.create_run_failure_for_tool_run(
        tool_run_id=uuid4(),
        correlation_id=uuid4(),
        error_type="E",
        error={},
    )
    assert rid is not None


@pytest.mark.asyncio
async def test_create_response_artifact_for_tool_run(exec_repo: ExecutionRepository) -> None:
    fid = uuid4()
    iid = uuid4()
    fr = MagicMock()
    fr.interaction_id = iid
    exec_repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=fid)
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    rid = await exec_repo.create_response_artifact_for_tool_run(
        tool_run_id=uuid4(), payload={}
    )
    assert rid is not None


@pytest.mark.asyncio
async def test_create_response_artifact_for_flow_run(exec_repo: ExecutionRepository) -> None:
    fr = MagicMock()
    fr.interaction_id = uuid4()
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    rid = await exec_repo.create_response_artifact_for_flow_run(
        flow_run_id=uuid4(), payload={}
    )
    assert rid is not None


@pytest.mark.asyncio
async def test_create_response_artifact_missing_interaction(
    exec_repo: ExecutionRepository,
) -> None:
    fr = MagicMock()
    fr.interaction_id = None
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    with pytest.raises(DomainValidationException, match="flow_run_missing_interaction"):
        await exec_repo.create_response_artifact_for_flow_run(
            flow_run_id=uuid4(), payload={}
        )


@pytest.mark.asyncio
async def test_create_tool_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    tid = await exec_repo.create_tool_run(
        tool_config_id=uuid4(),
        correlation_id=uuid4(),
        agent_run_id=None,
        node_run_id=uuid4(),
        idempotency_key=None,
        has_side_effect=False,
        input_payload={},
    )
    assert tid is not None


@pytest.mark.asyncio
async def test_create_node_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    nid = await exec_repo.create_node_run(
        flow_run_id=uuid4(),
        node_id=uuid4(),
        correlation_id=uuid4(),
        input_payload={},
        output_payload={},
        status="RUNNING",
        canonical_status="RUNNING",
    )
    assert nid is not None


@pytest.mark.asyncio
async def test_update_node_run_result(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.update_node_run_result(
        node_run_id=uuid4(),
        output_payload={},
        status="DONE",
        canonical_status="DONE",
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_node_run_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await exec_repo.update_node_run_result(
            node_run_id=uuid4(),
            output_payload={},
            status="X",
            canonical_status="X",
        )


# --- graph state ---


@pytest.mark.asyncio
async def test_get_graph_state_from_cache(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.execution.graph_state import GraphState as GraphStateModel

    d = {"flow_run_id": str(uuid4()), "state": {}, "last_node_run_id": None}
    exec_repo.cache_adapter.get = AsyncMock(return_value=d)
    with patch.object(GraphStateModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_graph_state(uuid4())


@pytest.mark.asyncio
async def test_get_graph_state_db_populates_cache(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    st = MagicMock()
    st.to_dict = MagicMock(return_value={"x": 1})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=st)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_graph_state(uuid4())
    assert out is st
    exec_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_graph_state_insert(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.upsert_graph_state(
        flow_run_id=uuid4(), state={"a": 1}, last_node_run_id=None
    )
    session.commit.assert_awaited_once()
    exec_repo.cache_adapter.delete.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_graph_state_update(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.upsert_graph_state(
        flow_run_id=uuid4(), state={"a": 2}, last_node_run_id=uuid4()
    )
    session.commit.assert_awaited_once()


# --- cached getters ---


@pytest.mark.asyncio
async def test_get_flow_version_cache_hit(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"flow_version_id": str(uuid4())})
    with patch.object(FlowVersionModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_flow_version(uuid4())


@pytest.mark.asyncio
async def test_get_active_flow_version_id_cache_hit(exec_repo: ExecutionRepository) -> None:
    tid = uuid4()
    exec_repo.cache_adapter.get = AsyncMock(
        return_value={"flow_version_id": str(uuid4())}
    )
    assert await exec_repo.get_active_flow_version_id(tid) is not None


@pytest.mark.asyncio
async def test_get_flow_graph_by_flow_version_cache(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"flow_graph_id": str(uuid4())})
    with patch.object(FlowGraphModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_flow_graph_by_flow_version(uuid4())


@pytest.mark.asyncio
async def test_get_flow_graph_snapshot_by_flow_version_cache(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.flow.flow_graph_snapshot import (
        FlowGraphSnapshot as FlowGraphSnapshotModel,
    )

    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(FlowGraphSnapshotModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_flow_graph_snapshot_by_flow_version(uuid4())


@pytest.mark.asyncio
async def test_get_flow_graph_snapshot_by_id(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_graph_snapshot(uuid4()) is row


@pytest.mark.asyncio
async def test_get_tool_config_cache_hit(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"tool_config_id": str(uuid4())})
    with patch.object(ToolConfigModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_tool_config(uuid4())


@pytest.mark.asyncio
async def test_get_agent_version_cache_hit(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"agent_version_id": str(uuid4())})
    with patch.object(AgentVersionModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_agent_version(uuid4())


@pytest.mark.asyncio
async def test_get_active_agent_version_id_cache_hit(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(
        return_value={"agent_version_id": str(uuid4())}
    )
    assert await exec_repo.get_active_agent_version_id(uuid4()) is not None


@pytest.mark.asyncio
async def test_get_ai_execution_policy_version_cache(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.ai_policy.execution_policy_version import (
        AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
    )

    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(AIExecutionPolicyVersionModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_ai_execution_policy_version(uuid4())


@pytest.mark.asyncio
async def test_get_model_cache_hit(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.ai_policy.model import Model as ModelModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"model_id": str(uuid4())})
    with patch.object(ModelModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_model(uuid4())


@pytest.mark.asyncio
async def test_get_node_cache_hit(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.flow.node import Node as NodeModel

    exec_repo.cache_adapter.get = AsyncMock(return_value={"node_id": str(uuid4())})
    with patch.object(NodeModel, "from_dict", return_value=MagicMock()):
        await exec_repo.get_node(uuid4())


@pytest.mark.asyncio
async def test_get_active_billing_policy_version_id_cache_hit(
    exec_repo: ExecutionRepository,
) -> None:
    vid = str(uuid4())
    exec_repo.cache_adapter.get = AsyncMock(
        return_value={"billing_policy_version_id": vid}
    )
    out = await exec_repo.get_active_billing_policy_version_id(uuid4())
    assert str(out) == vid


@pytest.mark.asyncio
async def test_get_active_memory_policy_version_id_cache_hit(
    exec_repo: ExecutionRepository,
) -> None:
    vid = str(uuid4())
    exec_repo.cache_adapter.get = AsyncMock(
        return_value={"memory_policy_version_id": vid}
    )
    out = await exec_repo.get_active_memory_policy_version_id(uuid4())
    assert str(out) == vid


@pytest.mark.asyncio
async def test_get_active_rag_policy_version_id_cache_hit(
    exec_repo: ExecutionRepository,
) -> None:
    vid = str(uuid4())
    exec_repo.cache_adapter.get = AsyncMock(return_value={"rag_policy_version_id": vid})
    out = await exec_repo.get_active_rag_policy_version_id(uuid4())
    assert str(out) == vid


# --- agent run ---


@pytest.mark.asyncio
async def test_get_agent_run_by_agent_version_and_flow(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert (
        await exec_repo.get_agent_run_by_agent_version_and_flow(uuid4(), uuid4()) is row
    )


@pytest.mark.asyncio
async def test_create_agent_run(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    rid = await exec_repo.create_agent_run(
        node_run_id=uuid4(),
        agent_version_id=uuid4(),
        correlation_id=uuid4(),
        input_payload={},
        model=None,
    )
    assert rid is not None


@pytest.mark.asyncio
async def test_update_agent_run_result(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    inst = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=inst)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.update_agent_run_result(
        agent_run_id=uuid4(),
        status="DONE",
        canonical_status="DONE",
        output={},
        error=None,
        input_tokens=1,
        output_tokens=2,
        estimated_cost=0.1,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_agent_run_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await exec_repo.update_agent_run_result(
            agent_run_id=uuid4(),
            status="X",
            canonical_status="X",
            output=None,
            error=None,
            input_tokens=None,
            output_tokens=None,
            estimated_cost=None,
        )


@pytest.mark.asyncio
async def test_acquire_flow_run_lock_creates_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(side_effect=[MagicMock(), lock_res])
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert (
        await exec_repo.acquire_flow_run_lock(uuid4(), "owner", uuid4()) is True
    )


@pytest.mark.asyncio
async def test_list_node_runs_with_flow_filter(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    n = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [n]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.list_node_runs(
        tenant_id=uuid4(), flow_run_id=uuid4(), limit=5
    )
    assert out == [n]


@pytest.mark.asyncio
async def test_list_agent_runs_no_flow_filter(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.list_agent_runs(tenant_id=uuid4(), flow_run_id=None) == []


# --- remaining branch coverage (push module toward ≥95%) ---


@pytest.mark.asyncio
async def test_upsert_preference_version_string_invalid(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {
        "profile_schema_version": 1,
        "memory_preferences": {
            "k": {"value": 1, "source": "a", "version": "not-a-number"},
        },
    }
    row.profile_version = 1
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=lock_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="k",
        preference_value=2,
        source="b",
        source_priority_map={"a": 1, "b": 2},
        ignore_if_unchanged=False,
    )


@pytest.mark.asyncio
async def test_upsert_preference_new_key_existing_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = {
        "profile_schema_version": 1,
        "memory_preferences": {"other": {"value": 1, "source": "s", "version": 1}},
    }
    row.profile_version = 1
    lock_res = MagicMock()
    lock_res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=lock_res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.upsert_user_preference_deterministic(
        tenant_id=uuid4(),
        user_id="u",
        preference_key="newkey",
        preference_value="v",
        source="src",
        source_priority_map={"src": 1},
        ignore_if_unchanged=False,
    )
    assert out.reason == "inserted"


@pytest.mark.asyncio
async def test_append_event_no_flow_run_id_returns_early(
    exec_repo: ExecutionRepository,
) -> None:
    eid = await exec_repo.append_execution_event(
        tenant_id=uuid4(),
        user_id="u",
        session_id=uuid4(),
        flow_run_id=None,  # type: ignore[arg-type]
        event_type="E",
        payload={},
        correlation_id=uuid4(),
    )
    assert eid is not None


@pytest.mark.asyncio
async def test_append_event_batching_creates_buffer_bucket(
    exec_repo: ExecutionRepository,
) -> None:
    fid = uuid4()
    exec_repo._batching_flow_runs.add(fid)
    exec_repo._event_batch_size = 99
    exec_repo._persist_execution_events_batch = AsyncMock()
    await exec_repo.append_execution_event(
        tenant_id=uuid4(),
        user_id="u",
        session_id=uuid4(),
        flow_run_id=fid,
        event_type="E",
        payload={},
        correlation_id=uuid4(),
    )
    assert fid in exec_repo._event_batch_buffer


@pytest.mark.asyncio
async def test_get_session_tracer_path(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    sess_row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=sess_row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_session(uuid4())
    assert out is sess_row


@pytest.mark.asyncio
async def test_get_flow_context_success(exec_repo: ExecutionRepository) -> None:
    sid, tid = uuid4(), uuid4()
    fr = MagicMock()
    fr.session_id = sid
    sr = MagicMock()
    sr.tenant_id = tid
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    exec_repo.get_session = AsyncMock(return_value=sr)
    assert await exec_repo.get_flow_context(uuid4()) == (sid, tid)


@pytest.mark.asyncio
async def test_get_user_preferences(exec_repo: ExecutionRepository) -> None:
    exec_repo.get_user_memory_profile = AsyncMock(
        return_value={"profile_schema_version": 1, "memory_preferences": {"z": {"value": 9}}}
    )
    prefs = await exec_repo.get_user_preferences(tenant_id=uuid4(), user_id="u")
    assert prefs["z"] == 9


@pytest.mark.asyncio
async def test_get_user_memory_profile_empty_row(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.profile = None
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_user_memory_profile(tenant_id=uuid4(), user_id="u") == {}


@pytest.mark.asyncio
async def test_get_flow_run_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    fr = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=fr)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_run(uuid4()) is fr


@pytest.mark.asyncio
async def test_get_interaction_metadata_full_dict(exec_repo: ExecutionRepository) -> None:
    fr = MagicMock()
    fr.interaction_id = uuid4()
    exec_repo.get_flow_run = AsyncMock(return_value=fr)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value={"a": 1})
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_interaction_metadata_for_flow_run(uuid4())
    assert out == {"a": 1}


@pytest.mark.asyncio
async def test_get_latest_waiting_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    u1 = uuid4()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [u1]
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
    assert cands == [u1]


@pytest.mark.asyncio
async def test_get_tool_run_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    tr = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=tr)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_tool_run(uuid4()) is tr


@pytest.mark.asyncio
async def test_get_active_billing_policy_version_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_billing_policy_version_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_billing_policy_version_miss_and_none(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_billing_policy_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_active_memory_policy_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_memory_policy_version_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_memory_policy_version_miss_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_memory_policy_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_active_rag_policy_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_rag_policy_version_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_rag_policy_version_miss_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_rag_policy_version(uuid4()) is None


@pytest.mark.asyncio
async def test_stamp_tool_run_billing_not_found(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with pytest.raises(NotFoundServiceException, match="tool_run_not_found"):
        await exec_repo.stamp_tool_run_billing_policy(
            tool_run_id=uuid4(), billing_policy_version_id=uuid4()
        )


@pytest.mark.asyncio
async def test_count_tool_runs_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one = MagicMock(return_value=5)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.count_tool_runs_for_flow_run(uuid4()) == 5


@pytest.mark.asyncio
async def test_count_agent_runs_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one = MagicMock(return_value=2)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.count_agent_runs_for_flow_run(uuid4()) == 2


@pytest.mark.asyncio
async def test_get_flow_run_id_node_run_missing(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = uuid4()
    tr.agent_run_id = None
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    exec_repo.get_node_run = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await exec_repo.get_flow_run_id_for_tool_run(uuid4())


@pytest.mark.asyncio
async def test_get_flow_run_id_agent_run_missing(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = None
    tr.agent_run_id = uuid4()
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    exec_repo.get_agent_run = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await exec_repo.get_flow_run_id_for_tool_run(uuid4())


@pytest.mark.asyncio
async def test_get_flow_run_id_agent_path_node_missing(exec_repo: ExecutionRepository) -> None:
    tr = MagicMock()
    tr.node_run_id = None
    tr.agent_run_id = uuid4()
    ar = MagicMock()
    ar.node_run_id = uuid4()
    exec_repo.get_tool_run = AsyncMock(return_value=tr)
    exec_repo.get_agent_run = AsyncMock(return_value=ar)
    exec_repo.get_node_run = AsyncMock(return_value=None)
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await exec_repo.get_flow_run_id_for_tool_run(uuid4())


@pytest.mark.asyncio
async def test_create_response_artifact_tool_run_flow_run_gone(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=uuid4())
    exec_repo.get_flow_run = AsyncMock(return_value=None)
    with pytest.raises(DomainValidationException, match="flow_run_missing_interaction"):
        await exec_repo.create_response_artifact_for_tool_run(
            tool_run_id=uuid4(), payload={}
        )


@pytest.mark.asyncio
async def test_create_node_run_without_tool_handle_raises(
    exec_repo: ExecutionRepository,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with patch.object(exec_repo.tracer, "observe", return_value=contextlib.nullcontext(None)):
        with pytest.raises(DomainValidationException, match="node_run_not_created"):
            await exec_repo.create_node_run(
                flow_run_id=uuid4(),
                node_id=uuid4(),
                correlation_id=uuid4(),
                input_payload={},
                output_payload={},
                status="RUNNING",
                canonical_status="RUNNING",
            )


@pytest.mark.asyncio
async def test_get_flow_version_db_miss(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_flow_returns_none(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow(uuid4()) is None


@pytest.mark.asyncio
async def test_get_active_flow_version_id_db_miss(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_flow_version_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_flow_graph_by_flow_version_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    g = MagicMock()
    g.to_dict = MagicMock(return_value={"flow_graph_id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=g)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_flow_graph_by_flow_version(uuid4())
    assert out is g
    exec_repo.cache_adapter.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_flow_graph_snapshot_by_flow_version_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    snap = MagicMock()
    snap.to_dict = MagicMock(return_value={"id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=snap)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    out = await exec_repo.get_flow_graph_snapshot_by_flow_version(uuid4())
    assert out is snap


@pytest.mark.asyncio
async def test_get_tool_config_db_miss(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_tool_config(uuid4()) is None


@pytest.mark.asyncio
async def test_get_agent_run_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    ar = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=ar)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_agent_run(uuid4()) is ar


@pytest.mark.asyncio
async def test_get_agent_version_db_caches(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel

    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    av = MagicMock()
    av.to_dict = MagicMock(return_value={"agent_version_id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=av)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with patch.object(AgentVersionModel, "from_dict", side_effect=lambda d: av):
        out = await exec_repo.get_agent_version(uuid4())
    assert out is av


@pytest.mark.asyncio
async def test_get_active_agent_version_id_db(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    vid = uuid4()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=vid)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_agent_version_id(uuid4()) == vid


@pytest.mark.asyncio
async def test_get_ai_execution_policy_version_db_caches(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.ai_policy.execution_policy_version import (
        AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
    )

    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    pol = MagicMock()
    pol.to_dict = MagicMock(return_value={"id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=pol)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with patch.object(AIExecutionPolicyVersionModel, "from_dict", side_effect=lambda d: pol):
        out = await exec_repo.get_ai_execution_policy_version(uuid4())
    assert out is pol


@pytest.mark.asyncio
async def test_get_model_db_caches(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.ai_policy.model import Model as ModelModel

    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    m = MagicMock()
    m.to_dict = MagicMock(return_value={"model_id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=m)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with patch.object(ModelModel, "from_dict", side_effect=lambda d: m):
        out = await exec_repo.get_model(uuid4())
    assert out is m


@pytest.mark.asyncio
async def test_get_node_run_traced(exec_repo: ExecutionRepository) -> None:
    session = AsyncMock()
    nr = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=nr)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_node_run(uuid4()) is nr


@pytest.mark.asyncio
async def test_get_node_db_caches(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.flow.node import Node as NodeModel

    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    node = MagicMock()
    node.to_dict = MagicMock(return_value={"node_id": str(uuid4())})
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=node)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    with patch.object(NodeModel, "from_dict", side_effect=lambda d: node):
        out = await exec_repo.get_node(uuid4())
    assert out is node


@pytest.mark.asyncio
async def test_get_billing_policy_version_cache_from_dict(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.governance.billing_policy_version import (
        BillingPolicyVersion as BillingPolicyVersionModel,
    )

    pol = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(BillingPolicyVersionModel, "from_dict", return_value=pol):
        assert await exec_repo.get_billing_policy_version(uuid4()) is pol


@pytest.mark.asyncio
async def test_get_memory_policy_version_cache_from_dict(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.governance.memory_policy_version import (
        MemoryPolicyVersion as MemoryPolicyVersionModel,
    )

    pol = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(MemoryPolicyVersionModel, "from_dict", return_value=pol):
        assert await exec_repo.get_memory_policy_version(uuid4()) is pol


@pytest.mark.asyncio
async def test_get_rag_policy_version_cache_from_dict(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.governance.rag_policy_version import (
        RagPolicyVersion as RagPolicyVersionModel,
    )

    pol = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(RagPolicyVersionModel, "from_dict", return_value=pol):
        assert await exec_repo.get_rag_policy_version(uuid4()) is pol


@pytest.mark.asyncio
async def test_get_flow_graph_by_flow_version_db_returns_none(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_graph_by_flow_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_flow_graph_snapshot_by_flow_version_db_returns_none(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_flow_graph_snapshot_by_flow_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_agent_version_cache_from_dict(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel

    av = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"agent_version_id": str(uuid4())})
    with patch.object(AgentVersionModel, "from_dict", return_value=av):
        assert await exec_repo.get_agent_version(uuid4()) is av


@pytest.mark.asyncio
async def test_get_agent_version_db_returns_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_agent_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_active_agent_version_id_db_returns_none(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_active_agent_version_id(uuid4()) is None


@pytest.mark.asyncio
async def test_get_ai_execution_policy_version_db_returns_none(
    exec_repo: ExecutionRepository,
) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_ai_execution_policy_version(uuid4()) is None


@pytest.mark.asyncio
async def test_get_ai_execution_policy_cache_from_dict(
    exec_repo: ExecutionRepository,
) -> None:
    from infra.database.models.ai_policy.execution_policy_version import (
        AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
    )

    pol = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"id": str(uuid4())})
    with patch.object(AIExecutionPolicyVersionModel, "from_dict", return_value=pol):
        assert await exec_repo.get_ai_execution_policy_version(uuid4()) is pol


@pytest.mark.asyncio
async def test_get_model_cache_from_dict(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.ai_policy.model import Model as ModelModel

    m = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"model_id": str(uuid4())})
    with patch.object(ModelModel, "from_dict", return_value=m):
        assert await exec_repo.get_model(uuid4()) is m


@pytest.mark.asyncio
async def test_get_model_db_returns_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_model(uuid4()) is None


@pytest.mark.asyncio
async def test_get_node_cache_from_dict(exec_repo: ExecutionRepository) -> None:
    from infra.database.models.flow.node import Node as NodeModel

    node = MagicMock()
    exec_repo.cache_adapter.get = AsyncMock(return_value={"node_id": str(uuid4())})
    with patch.object(NodeModel, "from_dict", return_value=node):
        assert await exec_repo.get_node(uuid4()) is node


@pytest.mark.asyncio
async def test_get_node_db_returns_none(exec_repo: ExecutionRepository) -> None:
    exec_repo.cache_adapter.get = AsyncMock(return_value=None)
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=res)
    exec_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await exec_repo.get_node(uuid4()) is None
