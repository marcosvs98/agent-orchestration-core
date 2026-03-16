import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.nodes.clarification import ClarificationNode
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMResult
from domain.prompts.schemas.prompt import ResolvedPrompt


class _FakeTracer:
    @contextlib.contextmanager
    def observe(self, *, as_type, name, input, **kwargs):
        yield MagicMock(success=MagicMock(), update=MagicMock())


@pytest.fixture
def tracer():
    return _FakeTracer()


@pytest.fixture
def prompt_resolver():
    resolver = AsyncMock()
    resolver.resolve = AsyncMock(
        return_value=ResolvedPrompt(
            prompt_text="Test prompt",
            input_schema={},
            output_schema={},
            prompt_id=uuid4(),
            prompt_version=1,
            prompt_frozen_hash="abc",
        )
    )
    return resolver


@pytest.fixture
def llm_executor():
    return AsyncMock()


@pytest.fixture
def context():
    return ExecutionContext(
        tenant_id=uuid4(),
        interaction_id=uuid4(),
        user_id="user-1",
        session_id=uuid4(),
        input_payload={"user_input": "help me"},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
    )


@pytest.mark.asyncio
async def test_extra_system_context_merged_into_llm_request(
    tracer, prompt_resolver, llm_executor, context
) -> None:
    llm_executor.execute_llm = AsyncMock(
        return_value=LLMResult(output={"message": "ok"})
    )
    node = ClarificationNode(
        tracer=tracer,
        llm_executor=llm_executor,
        prompt_resolver=prompt_resolver,
    )
    config = {
        "llm": {"model_alias": "test-model"},
        "extra_system_context": "Current SLA Ticket\nticket: 4383ad2-f60a-4b16-8f9f-5bc4e4df47d5\ncurrent_priority: low",
    }
    context.metadata = {"runtime_policy": {"llm": {"model_alias": "test-model"}}}

    await node.execute(context, config)

    call_args = llm_executor.execute_llm.call_args
    request = call_args.kwargs["request"]
    assert request.system_context is not None
    assert "Current SLA Ticket" in request.system_context
    assert "current_priority: low" in request.system_context
    assert "4383ad2-f60a-4b16-8f9f-5bc4e4df47d5" in request.system_context


@pytest.mark.asyncio
async def test_extra_system_context_appended_to_existing_context(
    tracer, prompt_resolver, llm_executor, context
) -> None:
    llm_executor.execute_llm = AsyncMock(
        return_value=LLMResult(output={})
    )
    node = ClarificationNode(
        tracer=tracer,
        llm_executor=llm_executor,
        prompt_resolver=prompt_resolver,
    )
    context.system_context = "Existing context line"
    config = {
        "llm": {"model_alias": "test-model"},
        "extra_system_context": "Current SLA Ticket\nticket: x\ncurrent_priority: medium",
    }
    context.metadata = {"runtime_policy": {"llm": {"model_alias": "test-model"}}}

    await node.execute(context, config)

    request = llm_executor.execute_llm.call_args.kwargs["request"]
    assert "Existing context line" in request.system_context
    assert "Current SLA Ticket" in request.system_context
    assert "current_priority: medium" in request.system_context
