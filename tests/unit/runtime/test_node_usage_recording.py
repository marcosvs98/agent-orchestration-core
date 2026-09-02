"""Per-node spend accounting (gap register §3).

`agent_run.input_tokens` / `output_tokens` / `estimated_cost` existed but were never written by the
graph runtime, and there was no durable per-tenant ledger at all. The step runner now writes both
after every node that reports usage.
"""

from __future__ import annotations

import contextlib
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.node_step_runner import NodeStepRunner
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.execution.services.state_machine import AgentRunStatus
from domain.llm.schemas.usage import LLMUsageRecord
from domain.prompts.schemas.prompt import NodeType

TENANT_ID = uuid4()
FLOW_RUN_ID = uuid4()
SESSION_ID = uuid4()
NODE_RUN_ID = uuid4()
AGENT_VERSION_ID = uuid4()


def _tracer() -> MagicMock:
    tracer = MagicMock()
    tracer.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return tracer


def _repository() -> MagicMock:
    repository = MagicMock()
    repository.create_agent_run = AsyncMock(return_value=uuid4())
    repository.update_agent_run_result = AsyncMock()
    repository.record_llm_usage = AsyncMock(return_value=uuid4())
    return repository


def _context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=TENANT_ID,
        interaction_id=uuid4(),
        user_id="u",
        session_id=SESSION_ID,
        input_payload={},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=FLOW_RUN_ID,
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
    )


def _runner(repository: MagicMock) -> NodeStepRunner:
    return NodeStepRunner(repository=repository, tracer=_tracer(), registry=MagicMock())


def _result(usage: LLMUsageRecord | None) -> NodeResult:
    return NodeResult(
        node=NodeType.IntentClassifier,
        status=NodeExecutionStatus.SUCCESS,
        data={"intent": "x"},
        usage=usage,
    )


def _usage(**overrides) -> LLMUsageRecord:
    fields = dict(
        provider="OPENAI",
        provider_model="gpt-4o",
        task_type="intent_selection",
        inference_layer="LLM",
        input_tokens=120,
        output_tokens=30,
        cost_usd=Decimal("0.004500"),
        agent_version_id=AGENT_VERSION_ID,
        latency_ms=850,
    )
    fields.update(overrides)
    return LLMUsageRecord(**fields)


@pytest.mark.asyncio
async def test_ledger_row_carries_tokens_cost_and_attribution():
    repository = _repository()

    await _runner(repository)._record_usage(
        context=_context(), node_run_id=NODE_RUN_ID, node_result=_result(_usage())
    )

    kwargs = repository.record_llm_usage.await_args.kwargs
    assert kwargs["tenant_id"] == TENANT_ID
    assert kwargs["flow_run_id"] == FLOW_RUN_ID
    assert kwargs["node_run_id"] == NODE_RUN_ID
    assert kwargs["session_id"] == SESSION_ID
    assert kwargs["provider_model"] == "gpt-4o"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 30
    assert kwargs["cost_usd"] == Decimal("0.004500")
    assert kwargs["latency_ms"] == 850


@pytest.mark.asyncio
async def test_agent_run_is_created_and_populated_when_an_agent_governs_the_node():
    repository = _repository()

    await _runner(repository)._record_usage(
        context=_context(), node_run_id=NODE_RUN_ID, node_result=_result(_usage())
    )

    create = repository.create_agent_run.await_args.kwargs
    assert create["agent_version_id"] == AGENT_VERSION_ID
    assert create["node_run_id"] == NODE_RUN_ID
    assert create["model"] == "gpt-4o"

    update = repository.update_agent_run_result.await_args.kwargs
    assert update["input_tokens"] == 120
    assert update["output_tokens"] == 30
    assert update["estimated_cost"] == pytest.approx(0.0045)
    assert update["status"] == AgentRunStatus.COMPLETED


@pytest.mark.asyncio
async def test_ledger_links_the_agent_run_it_created():
    repository = _repository()
    agent_run_id = uuid4()
    repository.create_agent_run = AsyncMock(return_value=agent_run_id)

    await _runner(repository)._record_usage(
        context=_context(), node_run_id=NODE_RUN_ID, node_result=_result(_usage())
    )

    assert repository.record_llm_usage.await_args.kwargs["agent_run_id"] == agent_run_id


@pytest.mark.asyncio
async def test_node_without_an_agent_binding_still_lands_in_the_ledger():
    repository = _repository()

    await _runner(repository)._record_usage(
        context=_context(),
        node_run_id=NODE_RUN_ID,
        node_result=_result(_usage(agent_version_id=None)),
    )

    repository.create_agent_run.assert_not_called()
    assert repository.record_llm_usage.await_args.kwargs["agent_run_id"] is None


@pytest.mark.asyncio
async def test_cache_hits_are_recorded_at_zero_cost_and_marked_as_such():
    """A semantic-cache hit must be distinguishable from real provider spend."""

    repository = _repository()

    await _runner(repository)._record_usage(
        context=_context(),
        node_run_id=NODE_RUN_ID,
        node_result=_result(
            _usage(inference_layer="CACHE", cost_usd=Decimal("0"), input_tokens=0, output_tokens=0)
        ),
    )

    kwargs = repository.record_llm_usage.await_args.kwargs
    assert kwargs["inference_layer"] == "CACHE"
    assert kwargs["cost_usd"] == Decimal("0")


@pytest.mark.asyncio
async def test_non_llm_nodes_write_nothing():
    repository = _repository()

    await _runner(repository)._record_usage(
        context=_context(), node_run_id=NODE_RUN_ID, node_result=_result(None)
    )

    repository.record_llm_usage.assert_not_called()
    repository.create_agent_run.assert_not_called()


@pytest.mark.asyncio
async def test_accounting_failure_never_fails_the_node():
    """The node already produced its result; a ledger write must not undo that."""

    repository = _repository()
    repository.record_llm_usage = AsyncMock(side_effect=RuntimeError("db down"))

    await _runner(repository)._record_usage(
        context=_context(), node_run_id=NODE_RUN_ID, node_result=_result(_usage())
    )
