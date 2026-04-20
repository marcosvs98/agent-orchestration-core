import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.execution.schemas.trace import TraceContext
from domain.llm.schemas.llm import LLMRequest, LLMResult, LLMTaskType
from domain.llm.services.llm_executor import LLMExecutor
from domain.llm.services.provider_selector import LLMProviderSelection
from exceptions.service_exceptions import DomainValidationException


class _ObsHandle:
    def success(self, **kwargs: object) -> None:
        return None

    def error(self, **kwargs: object) -> None:
        return None

    def update(self, **kwargs: object) -> None:
        return None


def _fake_tracer() -> MagicMock:
    t = MagicMock()

    def _observe(**_kwargs: object) -> contextlib.AbstractContextManager[_ObsHandle]:
        return contextlib.nullcontext(_ObsHandle())

    t.observe.side_effect = _observe
    return t


class _Repo:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def append_execution_event(
        self,
        *,
        tenant_id,
        session_id,
        flow_run_id,
        event_type,
        payload,
        correlation_id,
        causation_id,
        schema_version,
        node_id=None,
        edge_id=None,
    ):
        self.events.append(event_type)


class _StubProvider:
    def __init__(self, *, output: dict, token_usage: dict) -> None:
        self._output = output
        self._token_usage = token_usage

    async def infer(self, request, on_delta=None):
        return LLMResult(
            output=self._output,
            token_usage=self._token_usage,
            model_alias=request.model_alias,
        )


@pytest.mark.asyncio
async def test_llm_executor_happy_path_emits_events():
    repo = _Repo()
    provider = _StubProvider(
        output={"result": "ok"},
        token_usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    )
    executor = LLMExecutor(repo, provider, tracer=_fake_tracer())
    request = LLMRequest(
        task_type=LLMTaskType.INTENT_SELECTION,
        input_payload={"anything": "goes"},
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        model_alias="fake-model",
    )
    trace = TraceContext(trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    result = await executor.execute_llm(
        request=request,
        trace=trace,
        tenant_id=trace.tenant_id,
        session_id=uuid.uuid4(),
        flow_run_id=trace.flow_run_id,
        correlation_id=uuid.uuid4(),
    )

    assert isinstance(result, LLMResult)
    assert result.output["result"] == "ok"
    assert "LLMCallStarted" in repo.events
    assert "LLMCallCompleted" in repo.events


@pytest.mark.asyncio
async def test_llm_executor_fails_on_output_schema_violation():
    repo = _Repo()
    provider = _StubProvider(
        output={"unexpected": True},
        token_usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    )
    selector_called: dict[str, str] = {}

    def provider_factory(selection: LLMProviderSelection):
        selector_called["provider_model"] = selection.provider_model
        return provider

    provider_selector = MagicMock()
    provider_selector.select = AsyncMock(
        return_value=LLMProviderSelection(
            provider="OPENAI",
            provider_model="fake-model",
        )
    )

    executor = LLMExecutor(
        repo,
        provider,
        provider_selector=provider_selector,
        provider_factory=provider_factory,
        tracer=_fake_tracer(),
    )

    request = LLMRequest(
        task_type=LLMTaskType.PARAM_EXTRACTION,
        input_payload={},
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"required_field": {"type": "string"}},
            "required": ["required_field"],
        },
        model_alias="fake-model",
    )
    trace = TraceContext(trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4())

    with pytest.raises(DomainValidationException):
        await executor.execute_llm(
            request=request,
            trace=trace,
            tenant_id=trace.tenant_id,
            session_id=uuid.uuid4(),
            flow_run_id=trace.flow_run_id,
            correlation_id=uuid.uuid4(),
        )

    assert "LLMCallFailed" in repo.events
