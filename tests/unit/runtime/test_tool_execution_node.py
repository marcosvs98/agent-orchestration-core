from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.execution.schemas.tool_schedule import ToolRunSchedule
from domain.execution.services.graph_runtime.nodes.tool_executor import ToolExecutor
from domain.execution.services.graph_runtime.types import ExecutionContext, NodeExecutionStatus
from domain.prompts.schemas.prompt import NodeType


class _FakeObservation:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, *args, **kwargs):
        pass


class _FakeTracer:
    def observe(self, *, as_type, name, input, metadata=None):
        return _FakeObservation()


def _make_context(*, state: dict, strict_mode: bool = False) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid4(),
        interaction_id=uuid4(),
        user_id="user-1",
        session_id=uuid4(),
        input_payload={},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        trace_id=uuid4(),
        current_node_id="node-1",
        current_node_run_id=uuid4(),
        state=state,
        metadata={
            "runtime_policy": {
                "execution": {"strict_contract_mode": strict_mode},
                "limits": {"tool_fanout_max_concurrency": 4},
            }
        },
    )


def _executor_with_mocks(orchestrator: AsyncMock) -> tuple[ToolExecutor, AsyncMock]:
    execution_repository = AsyncMock()
    execution_repository.create_tool_run = AsyncMock(return_value=uuid4())
    node = ToolExecutor(
        tool_orchestrator=orchestrator,
        execution_repository=execution_repository,
        tracer=_FakeTracer(),
    )
    return node, execution_repository


@pytest.mark.asyncio
async def test_tool_execution_node_strict_missing_tool_config_id_returns_error():
    state = {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                }
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "otherTool",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(uuid4()),
                    }
                }
            ]
        },
    }
    orchestrator = AsyncMock()
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state, strict_mode=True))

    assert result.status == NodeExecutionStatus.ERROR
    assert result.error is not None
    assert result.error["message"] == "ready_operation_tool_config_unresolved"
    orchestrator.execute_tool_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_execution_node_executes_only_ready_operations():
    tool_config_id = uuid4()
    state = {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                },
                {
                    "operation_id": "op_2",
                    "tool_name": "createExpense",
                    "status": "incomplete",
                    "params": {"amount": 11},
                },
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(tool_config_id),
                    }
                }
            ]
        },
    }
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(
        return_value={"status_code": 200, "body": {"ok": True}}
    )
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    rows = result.data["result"]
    assert len(rows) == 1
    assert rows[0]["operation_id"] == "op_1"
    assert rows[0]["tool_name"] == "createExpense"
    assert rows[0]["execution_mode"] == "immediate"
    assert rows[0]["status"] == "success"
    assert rows[0]["result"] == {"status_code": 200, "body": {"ok": True}}
    assert orchestrator.execute_tool_run.await_count == 1


@pytest.mark.asyncio
async def test_tool_execution_node_returns_success_for_empty_result():
    state = {
        NodeType.ToolInputFiller.value: {"result": []},
        NodeType.ToolResolver.value: {"result": []},
    }
    orchestrator = AsyncMock()
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data == {"result": []}
    assert NodeType.ToolExecutor.value in (result.next_state or {})
    orchestrator.execute_tool_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_execution_node_resolves_multi_tool_by_tool_name():
    cfg_a = uuid4()
    cfg_b = uuid4()
    state = {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_a",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                },
                {
                    "operation_id": "op_b",
                    "tool_name": "notifyExpense",
                    "status": "ready",
                    "params": {"channel": "sms"},
                },
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(cfg_a),
                    }
                },
                {
                    "selected_tool": {
                        "name": "notifyExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(cfg_b),
                    }
                },
            ]
        },
    }
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(
        side_effect=[
            {"status_code": 200, "body": {"expense_id": "exp_1"}},
            {"status_code": 200, "body": {"notification_id": "ntf_1"}},
        ]
    )
    node, execution_repository = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    called_tool_config_ids = {
        call.kwargs["tool_config_id"]
        for call in execution_repository.create_tool_run.await_args_list
    }
    assert called_tool_config_ids == {cfg_a, cfg_b}
    assert orchestrator.execute_tool_run.await_count == 2


@pytest.mark.asyncio
async def test_tool_execution_node_does_not_mutate_context_state():
    cfg = uuid4()
    state = {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                }
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(cfg),
                    }
                }
            ]
        },
    }
    state_before = {
        key: value.copy() if isinstance(value, dict) else value for key, value in state.items()
    }
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(
        return_value={"status_code": 200, "body": {"ok": True}}
    )
    context = _make_context(state=state)
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(context)

    assert context.state == state_before
    assert result.next_state is not None
    assert result.next_state is not context.state


def _two_ready_operations_state(tool_config_id) -> dict:
    return {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                },
                {
                    "operation_id": "op_2",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 20},
                },
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(tool_config_id),
                    }
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_retry_pass_reexecutes_only_the_flagged_operation():
    tool_config_id = uuid4()
    state = _two_ready_operations_state(tool_config_id)
    state["retry_operation_ids"] = ["op_2"]
    state["finalized_results"] = [
        {
            "operation_id": "op_1",
            "tool_name": "createExpense",
            "execution_mode": "immediate",
            "status": "success",
            "result": {"ok": True},
        }
    ]
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(return_value={"retried": True})
    node, repository = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state))

    assert orchestrator.execute_tool_run.await_count == 1
    assert repository.create_tool_run.await_count == 1
    by_id = {item["operation_id"]: item for item in result.data["result"]}
    assert set(by_id) == {"op_1", "op_2"}
    assert by_id["op_1"]["result"] == {"ok": True}
    assert by_id["op_2"]["result"] == {"retried": True}


@pytest.mark.asyncio
async def test_retry_pass_clears_the_retry_selection():
    tool_config_id = uuid4()
    state = _two_ready_operations_state(tool_config_id)
    state["retry_operation_ids"] = ["op_1"]
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(return_value={"ok": True})
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=state))

    assert (result.next_state or {})["retry_operation_ids"] == []


@pytest.mark.asyncio
async def test_first_pass_without_retry_selection_executes_every_ready_operation():
    tool_config_id = uuid4()
    orchestrator = AsyncMock()
    orchestrator.execute_tool_run = AsyncMock(return_value={"ok": True})
    node, _ = _executor_with_mocks(orchestrator)

    result = await node.execute(_make_context(state=_two_ready_operations_state(tool_config_id)))

    assert orchestrator.execute_tool_run.await_count == 2
    assert len(result.data["result"]) == 2


class _FakeScheduler:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests = []

    async def schedule_tool_run(self, *, request):  # noqa: ANN001, ANN201
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ToolRunSchedule(
            tool_run_id=request.tool_run_id,
            schedule_id=f"tool-run-{request.tool_run_id}",
            run_at=request.run_at,
        )

    async def cancel_tool_run_schedule(self, *, tool_run_id):  # noqa: ANN001, ANN201
        return None


def _one_ready_operation_state(tool_config_id, params=None) -> dict:
    return {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": params if params is not None else {"amount": 10},
                }
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": str(tool_config_id),
                    }
                }
            ]
        },
    }


def _scheduling_executor(scheduler):  # noqa: ANN001, ANN201
    orchestrator = AsyncMock()
    execution_repository = AsyncMock()
    execution_repository.create_tool_run = AsyncMock(return_value=uuid4())
    node = ToolExecutor(
        tool_orchestrator=orchestrator,
        execution_repository=execution_repository,
        tracer=_FakeTracer(),
        tool_run_scheduler=scheduler,
    )
    return node, orchestrator, execution_repository


@pytest.mark.asyncio
async def test_scheduled_mode_defers_execution_instead_of_calling_the_tool():
    scheduler = _FakeScheduler()
    node, orchestrator, repository = _scheduling_executor(scheduler)

    result = await node.execute(
        _make_context(state=_one_ready_operation_state(uuid4())),
        config={"scheduling": {"mode": "scheduled", "delay_seconds": 3600}},
    )

    orchestrator.execute_tool_run.assert_not_awaited()
    assert repository.create_tool_run.await_count == 1
    assert len(scheduler.requests) == 1
    entry = result.data["result"][0]
    assert entry["status"] == "scheduled"
    assert entry["execution_mode"] == "scheduled"
    assert entry["schedule_id"].startswith("tool-run-")
    assert entry["run_at"] is not None


@pytest.mark.asyncio
async def test_immediate_mode_is_the_default_and_executes_now():
    scheduler = _FakeScheduler()
    node, orchestrator, _ = _scheduling_executor(scheduler)
    orchestrator.execute_tool_run = AsyncMock(return_value={"ok": True})

    result = await node.execute(_make_context(state=_one_ready_operation_state(uuid4())))

    orchestrator.execute_tool_run.assert_awaited_once()
    assert scheduler.requests == []
    assert result.data["result"][0]["execution_mode"] == "immediate"


@pytest.mark.asyncio
async def test_scheduling_without_a_scheduler_reports_an_error_and_does_not_execute():
    node, orchestrator, _ = _scheduling_executor(None)

    result = await node.execute(
        _make_context(state=_one_ready_operation_state(uuid4())),
        config={"scheduling": {"mode": "scheduled", "delay_seconds": 60}},
    )

    orchestrator.execute_tool_run.assert_not_awaited()
    entry = result.data["result"][0]
    assert entry["status"] == "error"
    assert entry["result"]["message"] == "tool_scheduler_unavailable"


@pytest.mark.asyncio
async def test_run_at_param_in_the_past_is_rejected():
    scheduler = _FakeScheduler()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    node, orchestrator, _ = _scheduling_executor(scheduler)

    result = await node.execute(
        _make_context(state=_one_ready_operation_state(uuid4(), params={"when": past})),
        config={"scheduling": {"mode": "scheduled", "run_at_param": "when"}},
    )

    orchestrator.execute_tool_run.assert_not_awaited()
    assert scheduler.requests == []
    assert result.data["result"][0]["result"]["message"] == "tool_schedule_run_at_in_the_past"


@pytest.mark.asyncio
async def test_run_at_param_drives_the_schedule_time():
    scheduler = _FakeScheduler()
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    node, _, _ = _scheduling_executor(scheduler)

    result = await node.execute(
        _make_context(
            state=_one_ready_operation_state(uuid4(), params={"when": future.isoformat()})
        ),
        config={"scheduling": {"mode": "scheduled", "run_at_param": "when"}},
    )

    assert scheduler.requests[0].run_at == future
    assert result.data["result"][0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_tool_names_filter_leaves_unlisted_tools_immediate():
    scheduler = _FakeScheduler()
    node, orchestrator, _ = _scheduling_executor(scheduler)
    orchestrator.execute_tool_run = AsyncMock(return_value={"ok": True})

    result = await node.execute(
        _make_context(state=_one_ready_operation_state(uuid4())),
        config={
            "scheduling": {
                "mode": "scheduled",
                "delay_seconds": 60,
                "tool_names": ["someOtherTool"],
            }
        },
    )

    orchestrator.execute_tool_run.assert_awaited_once()
    assert scheduler.requests == []
    assert result.data["result"][0]["execution_mode"] == "immediate"


@pytest.mark.asyncio
async def test_invalid_scheduling_config_fails_the_node():
    node, orchestrator, _ = _scheduling_executor(_FakeScheduler())

    result = await node.execute(
        _make_context(state=_one_ready_operation_state(uuid4())),
        config={"scheduling": {"mode": "not-a-mode"}},
    )

    assert result.status == NodeExecutionStatus.ERROR
    assert result.error is not None
    assert result.error["message"] == "tool_scheduling_config_invalid"
    orchestrator.execute_tool_run.assert_not_awaited()
