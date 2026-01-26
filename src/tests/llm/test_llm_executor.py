import uuid

import pytest

from domain.execution.schemas.trace import TraceContext
from domain.llm.schemas.llm import LLMRequest, LLMTaskType, LLMResult
from domain.llm.services.fake_llm_provider import FakeLLMProvider
from domain.llm.services.llm_executor import LLMExecutor
from exceptions.service_exceptions import DomainValidationException
from domain.llm.services.provider_selector import LLMProviderSelection


class _Repo:
    def __init__(self) -> None:
        self.events = []

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


@pytest.mark.asyncio
async def test_llm_executor_happy_path_emits_events():
    repo = _Repo()
    provider = FakeLLMProvider(canned_output={"result": "ok"}, token_usage={"prompt_tokens": 5})
    executor = LLMExecutor(repo, provider)
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
    provider = FakeLLMProvider(canned_output={"unexpected": True})
    selector_called = {}

    async def provider_factory(selection: LLMProviderSelection):
        selector_called["provider_model"] = selection.provider_model
        return provider

    executor = LLMExecutor(
        repo,
        provider,
        provider_selector=None,
        provider_factory=provider_factory,
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
