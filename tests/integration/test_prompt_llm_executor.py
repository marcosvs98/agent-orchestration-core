from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from domain.execution.schemas.trace import TraceContext
from domain.llm.schemas.llm import LLMRequest, LLMResult, LLMTaskType
from domain.llm.services.llm_executor import LLMExecutor


class _ObsHandle:
    def success(self, **kwargs: object) -> None:
        return None

    def error(self, **kwargs: object) -> None:
        return None

    def update(self, **kwargs: object) -> None:
        return None


def _fake_tracer() -> MagicMock:
    import contextlib

    t = MagicMock()

    def _observe(**_kwargs: object):
        return contextlib.nullcontext(_ObsHandle())

    t.observe.side_effect = _observe
    return t


class _Repo:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def append_execution_event(self, **kwargs):
        self.events.append(kwargs.get("event_type"))


@pytest.mark.asyncio
async def test_llm_executor_emits_node_prompt_event_when_prompt_metadata_present():
    repo = _Repo()

    async def infer(request, on_delta=None):
        return LLMResult(
            output={"tool_id": "test_tool", "confidence": 0.9},
            token_usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            model_alias=request.model_alias,
        )

    provider = MagicMock()
    provider.infer = infer

    executor = LLMExecutor(repo, provider, tracer=_fake_tracer())
    request = LLMRequest(
        task_type=LLMTaskType.INTENT_SELECTION,
        input_payload={"user_input": "test"},
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"tool_id": {"type": "string"}, "confidence": {"type": "number"}},
            "required": ["tool_id", "confidence"],
        },
        model_alias="fake-model",
        prompt_version=1,
        prompt_frozen_hash="hash123",
    )
    trace = TraceContext(trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    await executor.execute_llm(
        request=request,
        trace=trace,
        tenant_id=trace.tenant_id,
        session_id=uuid.uuid4(),
        flow_run_id=trace.flow_run_id,
        correlation_id=uuid.uuid4(),
    )

    assert "NodePromptExecuted" in repo.events


@pytest.mark.asyncio
async def test_llm_executor_skips_node_prompt_event_without_prompt_metadata():
    repo = _Repo()

    async def infer(request, on_delta=None):
        return LLMResult(
            output={"result": "ok"},
            token_usage={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
            model_alias=request.model_alias,
        )

    provider = MagicMock()
    provider.infer = infer

    executor = LLMExecutor(repo, provider, tracer=_fake_tracer())
    request = LLMRequest(
        task_type=LLMTaskType.INTENT_SELECTION,
        input_payload={"test": "data"},
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        model_alias="fake-model",
    )
    trace = TraceContext(trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    await executor.execute_llm(
        request=request,
        trace=trace,
        tenant_id=trace.tenant_id,
        session_id=uuid.uuid4(),
        flow_run_id=trace.flow_run_id,
        correlation_id=uuid.uuid4(),
    )

    assert "NodePromptExecuted" not in repo.events
