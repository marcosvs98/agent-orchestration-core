import importlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from adapters.observability import langfuse_runtime_tracer as tracer_module
from exceptions.service_exceptions import DomainValidationException


def test_tracer_blocks_when_missing_config(monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", None)
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", None)
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", None)
    importlib.reload(tracer_module)
    with pytest.raises(DomainValidationException):
        tracer_module.LangfuseRuntimeTracer()


@patch("langfuse.get_client")
def test_tracer_creates_trace_context(mock_get_client, monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)

    mock_client = MagicMock()
    mock_client.create_trace_id = MagicMock(return_value=str(uuid4()))
    mock_get_client.return_value = mock_client

    tracer = tracer_module.LangfuseRuntimeTracer(environment="test", runtime_version="0.0.0")
    flow_run_id = uuid4()
    ctx = tracer.start_flow_trace(
        flow_run_id=flow_run_id,
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        tenant_id=uuid4(),
        session_id=None,
        user_id=None,
        trace_id=uuid4(),
    )
    assert ctx.trace_id is not None
    assert ctx.flow_run_id == flow_run_id
    assert ctx.root_observation_id is None

    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation = MagicMock(return_value=mock_span)
    mock_client.get_current_observation_id = MagicMock(return_value="obs_123")

    with tracer.start_flow_span(trace=ctx):
        assert ctx.root_observation_id is not None


@patch("langfuse.get_client")
def test_tracer_hierarchy_flow_node_llm(mock_get_client, monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_flow_span = MagicMock()
    mock_flow_span.__enter__ = MagicMock(return_value=mock_flow_span)
    mock_flow_span.__exit__ = MagicMock(return_value=False)
    mock_flow_span.update = MagicMock()

    mock_node_span = MagicMock()
    mock_node_span.__enter__ = MagicMock(return_value=mock_node_span)
    mock_node_span.__exit__ = MagicMock(return_value=False)
    mock_node_span.update = MagicMock()

    mock_generation = MagicMock()
    mock_generation.__enter__ = MagicMock(return_value=mock_generation)
    mock_generation.__exit__ = MagicMock(return_value=False)
    mock_generation.update = MagicMock()

    def mock_start_observation(**kwargs):
        if kwargs.get("as_type") == "span" and kwargs.get("name") == "flow-run":
            return mock_flow_span
        elif kwargs.get("as_type") == "span" and kwargs.get("name") == "node-execution":
            return mock_node_span
        elif kwargs.get("as_type") == "generation":
            return mock_generation
        return MagicMock()

    mock_client.start_as_current_observation = MagicMock(side_effect=mock_start_observation)
    mock_client.get_current_observation_id = MagicMock(return_value="obs_123")
    mock_client.flush = MagicMock()
    mock_client.shutdown = MagicMock()

    tracer = tracer_module.LangfuseRuntimeTracer(environment="test", runtime_version="0.0.0")
    trace_context = tracer.start_flow_trace(
        flow_run_id=uuid4(),
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        tenant_id=uuid4(),
        session_id=None,
        user_id=None,
    )

    with tracer.start_flow_span(trace=trace_context):
        with tracer.start_node_span(node_id="node1", node_type="IntentNode", input={}):
            with tracer.start_llm_generation(
                model_id="gpt-4",
                task_type="INTENT_SELECTION",
                input={},
            ) as handle:
                handle.update_success(
                    output={},
                    token_usage={"input": 10, "output": 20},
                    cost=0.002,
                    latency_ms=45,
                    model_version="1.0",
                )

    assert mock_client.start_as_current_observation.call_count >= 3
    mock_generation.update.assert_called_once()
    tracer.flush()
    mock_client.flush.assert_called_once()
    tracer.shutdown()
    mock_client.shutdown.assert_called_once()


@patch("langfuse.get_client")
def test_tracer_guardrail_span(mock_get_client, monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_guardrail_span = MagicMock()
    mock_guardrail_span.__enter__ = MagicMock(return_value=mock_guardrail_span)
    mock_guardrail_span.__exit__ = MagicMock(return_value=False)
    mock_guardrail_span.update = MagicMock()

    mock_client.start_as_current_observation = MagicMock(return_value=mock_guardrail_span)

    tracer = tracer_module.LangfuseRuntimeTracer(environment="test", runtime_version="0.0.0")

    with tracer.start_guardrail_span(guardrail_type="LLM", input={}) as handle:
        handle.update_decision(
            decision="ALLOW",
            reason_code="ALLOW",
            applied_limits={},
            overrides={},
        )

    mock_guardrail_span.update.assert_called_once()


@patch("langfuse.get_client")
def test_tracer_tool_span(mock_get_client, monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_tool_span = MagicMock()
    mock_tool_span.__enter__ = MagicMock(return_value=mock_tool_span)
    mock_tool_span.__exit__ = MagicMock(return_value=False)
    mock_tool_span.update = MagicMock()

    mock_client.start_as_current_observation = MagicMock(return_value=mock_tool_span)

    tracer = tracer_module.LangfuseRuntimeTracer(environment="test", runtime_version="0.0.0")

    with tracer.start_tool_span(tool_id="calculate-tax", input={}):
        pass

    mock_tool_span.update.assert_called_once()


@patch("langfuse.get_client")
def test_tracer_deterministic_trace_id(mock_get_client, monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)

    mock_client = MagicMock()
    deterministic_id = "deterministic_trace_123"
    mock_client.create_trace_id = MagicMock(return_value=deterministic_id)
    mock_get_client.return_value = mock_client

    tracer = tracer_module.LangfuseRuntimeTracer(environment="test", runtime_version="0.0.0")

    ctx = tracer.start_flow_trace(
        flow_run_id=uuid4(),
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        tenant_id=uuid4(),
        session_id=None,
        user_id=None,
        external_request_id="req_12345",
    )

    mock_client.create_trace_id.assert_called_once_with(seed="req_12345")
    assert str(ctx.trace_id) == deterministic_id
