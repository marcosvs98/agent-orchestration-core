import importlib
import os
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


def test_tracer_creates_trace_context(monkeypatch):
    monkeypatch.setattr(tracer_module, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(tracer_module, "LANGFUSE_HOST", "https://langfuse.local")
    importlib.reload(tracer_module)
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
    assert ctx.root_observation_id is not None
