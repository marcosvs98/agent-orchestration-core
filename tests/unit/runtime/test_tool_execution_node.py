from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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
