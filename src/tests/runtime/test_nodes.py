import uuid

import pytest

from domain.execution.services.graph_runtime.nodes import (
    ClarificationNode,
    FallbackNode,
    ResponseComposer,
    ToolExecutionNode,
    ToolSelectionNode,
)
from domain.execution.services.graph_runtime.types import ExecutionContext


@pytest.mark.asyncio
async def test_intent_tool_selection_node_executes_with_default():
    node = ToolSelectionNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    result = await node.execute(context)
    assert result.status == "SUCCESS"
    assert result.payload["validation_status"] == "VALID"
    assert result.payload["confidence"] == 1.0


@pytest.mark.asyncio
async def test_intent_tool_selection_node_executes_with_config():
    node = ToolSelectionNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"validation_status": "MISSING_FIELDS", "confidence": 0.5}}
    result = await node.execute(context, config)
    assert result.status == "SUCCESS"
    assert result.payload["validation_status"] == "MISSING_FIELDS"
    assert result.payload["confidence"] == 0.5


@pytest.mark.asyncio
async def test_tool_execution_node_executes_with_success():
    node = ToolExecutionNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"execution_status": "SUCCESS"}}
    result = await node.execute(context, config)
    assert result.status == "SUCCESS"
    assert result.payload["execution_status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_tool_execution_node_executes_with_error():
    node = ToolExecutionNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"execution_status": "ERROR"}}
    result = await node.execute(context, config)
    assert result.status == "ERROR"
    assert result.payload["execution_status"] == "ERROR"


@pytest.mark.asyncio
async def test_clarification_node_executes():
    node = ClarificationNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    result = await node.execute(context)
    assert result.status == "NEEDS_INPUT"
    assert "missing_fields" in result.payload
    assert "user_message" in result.payload


@pytest.mark.asyncio
async def test_clarification_node_executes_with_config():
    node = ClarificationNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"missing_fields": ["field1"], "user_message": "Please provide field1"}}
    result = await node.execute(context, config)
    assert result.status == "NEEDS_INPUT"
    assert result.payload["missing_fields"] == ["field1"]
    assert result.payload["user_message"] == "Please provide field1"


@pytest.mark.asyncio
async def test_response_node_executes():
    node = ResponseComposer()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    result = await node.execute(context)
    assert result.status == "SUCCESS"
    assert result.payload["message"] == "ok"
    assert "payload" in result.payload


@pytest.mark.asyncio
async def test_response_node_executes_with_config():
    node = ResponseComposer()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"message": "Custom response", "payload": {"data": "value"}}}
    result = await node.execute(context, config)
    assert result.status == "SUCCESS"
    assert result.payload["message"] == "Custom response"
    assert result.payload["payload"]["data"] == "value"


@pytest.mark.asyncio
async def test_fallback_node_executes():
    node = FallbackNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    result = await node.execute(context)
    assert result.status == "SUCCESS"
    assert result.payload["reason"] == "fallback"
    assert result.payload["message"] == "fallback"


@pytest.mark.asyncio
async def test_fallback_node_executes_with_config():
    node = FallbackNode()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id="test",
    )
    config = {"output": {"reason": "low_confidence", "message": "Unable to process"}}
    result = await node.execute(context, config)
    assert result.status == "SUCCESS"
    assert result.payload["reason"] == "low_confidence"
    assert result.payload["message"] == "Unable to process"


def test_node_attributes():
    assert ToolSelectionNode.node_type == "ToolSelectionNode"
    assert ToolSelectionNode.side_effect is False
    assert ToolSelectionNode.deterministic is False

    assert ToolExecutionNode.node_type == "ToolExecutionNode"
    assert ToolExecutionNode.side_effect is True
    assert ToolExecutionNode.deterministic is False

    assert ClarificationNode.node_type == "ClarificationNode"
    assert ClarificationNode.side_effect is False
    assert ClarificationNode.deterministic is True

    assert ResponseComposer.node_type == "ResponseNode"
    assert ResponseComposer.side_effect is False
    assert ResponseComposer.deterministic is True

    assert FallbackNode.node_type == "FallbackNode"
    assert FallbackNode.side_effect is False
    assert FallbackNode.deterministic is True
