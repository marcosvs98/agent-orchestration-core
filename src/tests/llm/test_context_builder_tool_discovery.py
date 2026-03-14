from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType
from domain.llm.services.context_builder import ContextBuilder
from domain.prompts.schemas.prompt import NodeType
from domain.tools.schemas.tools import AvailableTool


class _FakeTracer:
    def observe(self, *, as_type, name, input):
        return contextlib.nullcontext()


@pytest.mark.asyncio
async def test_build_template_context_no_longer_performs_retrieval_for_tool_selection():
    """ContextBuilder should not perform tool catalog retrieval anymore.

    Retrieval is now handled directly by ToolSelectionNode.
    """
    agent_version_id = uuid4()
    tenant_id = uuid4()
    rag_config_id = uuid4()

    tool_a = AvailableTool(name="tool-1", tool_id=uuid4(), tool_config_id=uuid4())
    tool_b = AvailableTool(name="tool-2", tool_id=uuid4(), tool_config_id=uuid4())

    agents_repository = MagicMock()
    agents_repository.get_agent_version = AsyncMock(
        return_value=SimpleNamespace(
            agent_id=uuid4(),
            rag_config_id=rag_config_id,
            persona_config={},
        )
    )
    agents_repository.get_agent = AsyncMock(
        return_value=SimpleNamespace(tenant_id=tenant_id)
    )
    tools_repository = MagicMock()

    context_builder = ContextBuilder(
        agents_repository=agents_repository,
        tools_repository=tools_repository,
        tracer=_FakeTracer(),
    )
    execution_context = ExecutionContext(
        tenant_id=tenant_id,
        user_id="user-1",
        session_id=uuid4(),
        input_payload={"user_input": "find the right tool"},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
        available_tools=[tool_a, tool_b],
        metadata={"current_node_type": NodeType.ToolSelectionNode},
    )

    result = await context_builder.build_template_context(
        agent_version_id=agent_version_id,
        task_type=LLMTaskType.TOOL_SELECTION,
        execution_context=execution_context,
        input_payload={"user_input": "find the right tool"},
        task_flags=None,
    )

    assert len(result["meta"]["available_tools"]) == 2
    assert "tool_candidate_evidence" not in result["meta"]
    assert len(execution_context.available_tools) == 2
