import contextlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.nodes.tool_execution import ToolExecutionNode
from domain.execution.services.graph_runtime.types import ExecutionContext, NodeExecutionStatus
from domain.prompts.schemas.prompt import NodeType


class _FakeTracer:
    def observe(self, *, as_type, name, input, metadata=None):
        return contextlib.nullcontext()


def _make_context(*, state: dict, strict_mode: bool = False) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid4(),
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


@pytest.mark.asyncio
async def test_tool_execution_node_strict_missing_tool_config_id_returns_error():
    state = {
        NodeType.ParamExtractionNode.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                }
            ]
        },
        NodeType.ToolSelectionNode.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                    }
                }
            ]
        },
    }
    orchestrator = AsyncMock()
    node = ToolExecutionNode(tracer=_FakeTracer(), tool_orchestrator=orchestrator)

    result = await node.execute(_make_context(state=state, strict_mode=True))

    assert result.status == NodeExecutionStatus.ERROR
    assert result.error is not None
    assert result.error["message"] == "ready_operation_tool_config_unresolved"
    orchestrator.execute_operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_execution_node_executes_only_ready_operations():
    tool_config_id = uuid4()
    state = {
        NodeType.ParamExtractionNode.value: {
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
        NodeType.ToolSelectionNode.value: {
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
    orchestrator.execute_operation = AsyncMock(
        return_value=(uuid4(), {"status_code": 200, "body": {"ok": True}})
    )
    node = ToolExecutionNode(tracer=_FakeTracer(), tool_orchestrator=orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["results"] == [
        {
            "operation_id": "op_1",
            "tool_name": "createExpense",
            "execution_mode": "immediate",
            "status": "success",
            "data": {"status_code": 200, "body": {"ok": True}},
        }
    ]
    assert orchestrator.execute_operation.await_count == 1


@pytest.mark.asyncio
async def test_tool_execution_node_returns_success_for_empty_result():
    state = {
        NodeType.ParamExtractionNode.value: {"result": []},
        NodeType.ToolSelectionNode.value: {"result": []},
    }
    orchestrator = AsyncMock()
    node = ToolExecutionNode(tracer=_FakeTracer(), tool_orchestrator=orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data == {"results": []}
    assert NodeType.ToolExecutionNode.value in (result.next_state or {})
    orchestrator.execute_operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_execution_node_resolves_multi_tool_by_tool_name():
    cfg_a = uuid4()
    cfg_b = uuid4()
    state = {
        NodeType.ParamExtractionNode.value: {
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
        NodeType.ToolSelectionNode.value: {
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
    orchestrator.execute_operation = AsyncMock(
        side_effect=[
            (uuid4(), {"status_code": 200, "body": {"expense_id": "exp_1"}}),
            (uuid4(), {"status_code": 200, "body": {"notification_id": "ntf_1"}}),
        ]
    )
    node = ToolExecutionNode(tracer=_FakeTracer(), tool_orchestrator=orchestrator)

    result = await node.execute(_make_context(state=state))

    assert result.status == NodeExecutionStatus.SUCCESS
    called_tool_config_ids = {
        call.kwargs["tool_config_id"] for call in orchestrator.execute_operation.await_args_list
    }
    assert called_tool_config_ids == {cfg_a, cfg_b}


@pytest.mark.asyncio
async def test_tool_execution_node_does_not_mutate_context_state():
    cfg = uuid4()
    state = {
        NodeType.ParamExtractionNode.value: {
            "result": [
                {
                    "operation_id": "op_1",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                }
            ]
        },
        NodeType.ToolSelectionNode.value: {
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
    orchestrator.execute_operation = AsyncMock(
        return_value=(uuid4(), {"status_code": 200, "body": {"ok": True}})
    )
    context = _make_context(state=state)
    node = ToolExecutionNode(tracer=_FakeTracer(), tool_orchestrator=orchestrator)

    result = await node.execute(context)

    assert context.state == state_before
    assert result.next_state is not None
    assert result.next_state is not context.state
