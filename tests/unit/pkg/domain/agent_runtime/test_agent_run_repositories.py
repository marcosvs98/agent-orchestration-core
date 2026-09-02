"""Agent run and delegation persistence with a mocked session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.agents.repositories.agent_delegation_repository import AgentDelegationRepository
from domain.execution.repositories.agent_run_repository import AgentRunRepository
from domain.execution.schemas.agent_run import AgentRunOrigin
from domain.execution.services.state_machine import AgentRunStatus, RunStatus
from exceptions.service_exceptions import NotFoundServiceException


def _session_cm(session: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _scalar_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    result.scalar_one = MagicMock(return_value=value)
    return result


def _scalars_result(values: list) -> MagicMock:
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=values)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    return result


@pytest.fixture
def agent_run_repo(tracer) -> AgentRunRepository:
    return AgentRunRepository(MagicMock(), tracer=tracer)


@pytest.fixture
def delegation_repo(tracer) -> AgentDelegationRepository:
    return AgentDelegationRepository(MagicMock(), tracer=tracer)


def _bind(repo, session: AsyncMock) -> None:
    repo.db.get_session = MagicMock(return_value=_session_cm(session))


@pytest.mark.asyncio
async def test_create_agent_run_defaults_the_root_to_itself(agent_run_repo, tenant_id) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    _bind(agent_run_repo, session)

    agent_run_id = await agent_run_repo.create_agent_run(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        agent_version_id=uuid4(),
        correlation_id=uuid4(),
        origin=AgentRunOrigin.DIRECT,
        input_payload={"instruction": "x"},
        context_snapshot={"items": []},
        tool_grant={"tools": []},
        max_iterations=5,
        model="gpt-4.1",
        billing_policy_version_id=uuid4(),
        ai_execution_policy_version_id=uuid4(),
        system_prompt_hash=None,
        runtime_snapshot={},
        runtime_snapshot_hash=None,
    )

    added = session.add.call_args.args[0]
    assert added.agent_run_id == agent_run_id
    assert added.root_agent_run_id == agent_run_id
    assert added.node_run_id is None
    assert added.canonical_status == AgentRunStatus.CREATED.value


@pytest.mark.asyncio
async def test_get_agent_run_is_scoped_to_the_tenant(agent_run_repo, tenant_id) -> None:
    session = AsyncMock()
    row = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(row))
    _bind(agent_run_repo, session)

    assert await agent_run_repo.get_agent_run(tenant_id=tenant_id, agent_run_id=uuid4()) is row


@pytest.mark.asyncio
async def test_list_agent_runs_accepts_every_filter(agent_run_repo, tenant_id) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([MagicMock()]))
    _bind(agent_run_repo, session)

    rows = await agent_run_repo.list_agent_runs(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        flow_run_id=uuid4(),
        root_agent_run_id=uuid4(),
        parent_agent_run_id=uuid4(),
        limit=10,
    )

    assert len(rows) == 1


@pytest.mark.asyncio
async def test_mark_running_stamps_the_start(agent_run_repo) -> None:
    session = AsyncMock()
    instance = MagicMock()
    session.get = AsyncMock(return_value=instance)
    _bind(agent_run_repo, session)

    await agent_run_repo.mark_running(agent_run_id=uuid4())

    assert instance.status == RunStatus.RUNNING.value
    assert instance.canonical_status == AgentRunStatus.RUNNING.value
    assert instance.started_at is not None


@pytest.mark.asyncio
async def test_mark_running_on_a_missing_run_is_not_found(agent_run_repo) -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    _bind(agent_run_repo, session)

    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await agent_run_repo.mark_running(agent_run_id=uuid4())


@pytest.mark.asyncio
async def test_finish_agent_run_writes_the_terminal_state(agent_run_repo) -> None:
    session = AsyncMock()
    instance = MagicMock()
    session.get = AsyncMock(return_value=instance)
    _bind(agent_run_repo, session)

    await agent_run_repo.finish_agent_run(
        agent_run_id=uuid4(),
        status=RunStatus.COMPLETED.value,
        canonical_status=AgentRunStatus.COMPLETED.value,
        output={"text": "done"},
        error={},
        finish_reason="FINAL_OUTPUT",
        iterations_used=2,
        input_tokens=10,
        output_tokens=4,
        estimated_cost=0.01,
    )

    assert instance.canonical_status == AgentRunStatus.COMPLETED.value
    assert instance.output == {"text": "done"}
    assert instance.iterations_used == 2
    assert instance.finished_at is not None


@pytest.mark.asyncio
async def test_finish_agent_run_on_a_missing_run_is_not_found(agent_run_repo) -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    _bind(agent_run_repo, session)

    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await agent_run_repo.finish_agent_run(
            agent_run_id=uuid4(),
            status=RunStatus.FAILED.value,
            canonical_status=AgentRunStatus.FAILED.value,
            output={},
            error={},
            finish_reason=None,
            iterations_used=0,
            input_tokens=None,
            output_tokens=None,
            estimated_cost=None,
        )


@pytest.mark.asyncio
async def test_appended_rows_take_the_next_sequence(agent_run_repo, tenant_id) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(7))
    _bind(agent_run_repo, session)
    agent_run_id = uuid4()

    message_sequence = await agent_run_repo.append_message(
        agent_run_id=agent_run_id, role="assistant", content="hi"
    )
    event_sequence = await agent_run_repo.append_event(
        agent_run_id=agent_run_id,
        tenant_id=tenant_id,
        event_type="AgentRunStarted",
        payload={},
        correlation_id=uuid4(),
    )
    artifact_index = await agent_run_repo.append_artifact(
        agent_run_id=agent_run_id,
        name="final-output",
        description=None,
        parts=[{"kind": "text", "text": "x"}],
        payload={"text": "x"},
    )

    assert (message_sequence, event_sequence, artifact_index) == (8, 8, 8)


@pytest.mark.asyncio
async def test_transcript_reads_are_ordered_queries(agent_run_repo) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_result([MagicMock()]))
    _bind(agent_run_repo, session)
    agent_run_id = uuid4()

    assert len(await agent_run_repo.list_messages(agent_run_id=agent_run_id)) == 1
    assert len(await agent_run_repo.list_events(agent_run_id=agent_run_id)) == 1
    assert len(await agent_run_repo.list_artifacts(agent_run_id=agent_run_id)) == 1
    assert len(await agent_run_repo.list_tool_runs(agent_run_id=agent_run_id)) == 1


@pytest.mark.asyncio
async def test_create_delegation_starts_in_submitted(delegation_repo, tenant_id) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    _bind(delegation_repo, session)

    agent_delegation_id = await delegation_repo.create_delegation(
        tenant_id=tenant_id,
        parent_agent_run_id=uuid4(),
        target_agent_id=uuid4(),
        transport="internal",
        remote_endpoint=None,
        a2a_task_id="t-1",
        a2a_context_id="c-1",
        a2a_task_state="submitted",
        request_message={},
        correlation_id=uuid4(),
    )

    added = session.add.call_args.args[0]
    assert added.agent_delegation_id == agent_delegation_id
    assert added.a2a_task_state == "submitted"
    assert added.started_at is not None


@pytest.mark.asyncio
async def test_update_delegation_result_is_a_no_op_when_the_row_is_gone(
    delegation_repo,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    _bind(delegation_repo, session)

    await delegation_repo.update_delegation_result(
        agent_delegation_id=uuid4(),
        a2a_task_state="completed",
        child_agent_run_id=uuid4(),
        result={},
        error={},
        finished=True,
    )

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_delegation_result_writes_the_terminal_state(delegation_repo) -> None:
    session = AsyncMock()
    instance = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(instance))
    _bind(delegation_repo, session)
    child_agent_run_id = uuid4()

    await delegation_repo.update_delegation_result(
        agent_delegation_id=uuid4(),
        a2a_task_state="completed",
        child_agent_run_id=child_agent_run_id,
        result={"kind": "task"},
        error={},
        finished=True,
    )

    assert instance.a2a_task_state == "completed"
    assert instance.child_agent_run_id == child_agent_run_id
    assert instance.finished_at is not None


@pytest.mark.asyncio
async def test_delegations_can_be_read_back_by_task_id_and_parent(
    delegation_repo, tenant_id
) -> None:
    session = AsyncMock()
    row = MagicMock()
    session.execute = AsyncMock(side_effect=[_scalar_result(row), _scalars_result([row])])
    _bind(delegation_repo, session)

    assert (
        await delegation_repo.get_delegation_by_task_id(tenant_id=tenant_id, a2a_task_id="t-1")
        is row
    )
    assert await delegation_repo.list_delegations_for_agent_run(parent_agent_run_id=uuid4()) == [
        row
    ]
