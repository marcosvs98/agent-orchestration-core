"""BDD: deterministic node behaviour (ToolErrorHandler, IntentClassifier metadata)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from pytest_bdd import given, scenarios, then, when

pytestmark = pytest.mark.bdd

from domain.execution.services.graph_runtime.nodes.intent_classifier import (
    IntentClassifier,
)
from domain.execution.services.graph_runtime.nodes.tool_error_handler import (
    ToolErrorHandlerNode,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    OperationStatus,
)
from domain.prompts.schemas.prompt import NodeType

FEATURE = Path(__file__).parent / "features" / "graph_runtime_nodes.feature"

scenarios(str(FEATURE))


def _ctx(**kwargs: object) -> ExecutionContext:
    defaults: dict[str, object] = {
        "tenant_id": uuid4(),
        "interaction_id": uuid4(),
        "user_id": "u1",
        "session_id": uuid4(),
        "input_payload": None,
        "flow_id": uuid4(),
        "flow_version_id": uuid4(),
        "flow_run_id": uuid4(),
        "correlation_id": uuid4(),
        "current_node_id": "n1",
    }
    defaults.update(kwargs)
    return ExecutionContext.model_validate(defaults)


@given("a tool error handler node")
def _tool_err_node(bdd):
    bdd.tool_error_node = ToolErrorHandlerNode()


@given("a failed tool operation below max retries")
def _failed_op(bdd):
    op = str(uuid4())
    bdd.retry_op_id = op
    bdd.tool_error_ctx = _ctx(state={"retry_counts": {}})
    bdd.tool_error_ctx.state[NodeType.ToolExecutor.value] = {
        "result": [
            {
                "operation_id": op,
                "status": OperationStatus.ERROR.value,
            }
        ]
    }


@when("the node executes")
def _run_tool_error(bdd):
    bdd.tool_error_result = asyncio.run(
        bdd.tool_error_node.execute(bdd.tool_error_ctx, {"max_retries": 2})
    )


@then("the result asks for a retry of that operation")
def _assert_retry(bdd):
    assert bdd.retry_op_id in bdd.tool_error_result.data["retry_operation_ids"]


@given("the IntentClassifier node class")
def _ic_class(bdd):
    bdd.intent_classifier = IntentClassifier


@then("its node type is IntentClassifier")
def _assert_ic_type(bdd):
    assert bdd.intent_classifier.node_type == NodeType.IntentClassifier
