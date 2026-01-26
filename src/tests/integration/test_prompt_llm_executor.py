from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.trace import TraceContext
from domain.llm.schemas.llm import LLMRequest, LLMTaskType, LLMResult
from domain.llm.services.fake_llm_provider import FakeLLMProvider
from domain.llm.services.llm_executor import LLMExecutor
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType
from domain.prompts.services.prompt_service import PromptService


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
        self.events.append((event_type, payload))


@pytest.mark.asyncio
async def test_llm_executor_uses_dynamic_prompt_when_available():
    repo = _Repo()
    provider = FakeLLMProvider(
        canned_output={"tool_id": "test_tool", "confidence": 0.9},
        token_usage={"input_tokens": 10, "output_tokens": 5},
    )

    prompt_id = uuid4()
    prompt = NodePrompt(
        prompt_id=prompt_id,
        node_type=NodeType.IntentToolSelectionNode.value,
        template_text="Dynamic prompt: {user_input}",
        input_schema_id=None,
        output_schema_id=None,
        version=1,
        frozen_hash="hash123",
        is_active=True,
        description=None,
        created_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    prompt_repo = MagicMock(spec=PromptRepository)
    prompt_repo.get_active_prompt = AsyncMock(return_value=prompt)
    prompt_service = PromptService(repository=prompt_repo)

    executor = LLMExecutor(
        repo,
        provider,
        prompt_service=prompt_service,
    )

    request = LLMRequest(
        task_type=LLMTaskType.INTENT_SELECTION,
        input_payload={"user_input": "test"},
        input_schema={},
        output_schema={},
        model_alias="fake-model",
    )
    trace = TraceContext(
        trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4()
    )

    result = await executor.execute_llm(
        request=request,
        trace=trace,
        tenant_id=trace.tenant_id,
        session_id=uuid4(),
        flow_run_id=trace.flow_run_id,
        correlation_id=uuid4(),
    )

    assert isinstance(result, LLMResult)
    assert "LLMCallStarted" in [e[0] for e in repo.events]
    assert "LLMCallCompleted" in [e[0] for e in repo.events]
    assert "NodePromptExecuted" in [e[0] for e in repo.events]

    node_prompt_executed = next(
        (e for e in repo.events if e[0] == "NodePromptExecuted"), None
    )
    assert node_prompt_executed is not None
    assert node_prompt_executed[1]["node_type"] == NodeType.IntentToolSelectionNode.value
    assert node_prompt_executed[1]["prompt_version"] == 1
    assert node_prompt_executed[1]["frozen_hash"] == "hash123"


@pytest.mark.asyncio
async def test_llm_executor_falls_back_to_default_when_prompt_not_found():
    repo = _Repo()
    provider = FakeLLMProvider(
        canned_output={"result": "ok"},
        token_usage={"input_tokens": 5, "output_tokens": 3},
    )

    prompt_repo = MagicMock(spec=PromptRepository)
    prompt_repo.get_active_prompt = AsyncMock(return_value=None)
    prompt_service = PromptService(repository=prompt_repo)

    executor = LLMExecutor(
        repo,
        provider,
        prompt_service=prompt_service,
    )

    request = LLMRequest(
        task_type=LLMTaskType.INTENT_SELECTION,
        input_payload={"test": "data"},
        input_schema={},
        output_schema={},
        model_alias="fake-model",
    )
    trace = TraceContext(
        trace_id=uuid.uuid4(), flow_run_id=uuid.uuid4(), tenant_id=uuid.uuid4()
    )

    result = await executor.execute_llm(
        request=request,
        trace=trace,
        tenant_id=trace.tenant_id,
        session_id=uuid4(),
        flow_run_id=trace.flow_run_id,
        correlation_id=uuid4(),
    )

    assert isinstance(result, LLMResult)
    assert "LLMCallStarted" in [e[0] for e in repo.events]
    assert "LLMCallCompleted" in [e[0] for e in repo.events]
    assert "NodePromptExecuted" not in [e[0] for e in repo.events]
