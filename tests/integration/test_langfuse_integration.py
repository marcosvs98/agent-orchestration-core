from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer


@pytest.fixture
def tracer_off() -> LangfuseRuntimeTracer:
    """Tracer with Langfuse client disabled (no env keys required in CI)."""
    with patch("adapters.observability.langfuse_runtime_tracer.TRACING_ENABLED", False):
        yield LangfuseRuntimeTracer()


def test_langfuse_runtime_tracer_flush_shutdown_noop_when_disabled(tracer_off: LangfuseRuntimeTracer) -> None:
    tracer_off.flush()
    tracer_off.shutdown()


def test_start_flow_trace_uses_flow_run_id_when_tracing_disabled(
    tracer_off: LangfuseRuntimeTracer,
) -> None:
    flow_run_id = uuid4()
    ctx = tracer_off.start_flow_trace(
        flow_run_id=flow_run_id,
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        tenant_id=uuid4(),
        session_id=None,
        user_id=None,
    )
    assert ctx.flow_run_id == flow_run_id
    assert ctx.trace_id == flow_run_id
