from __future__ import annotations

# import orjson
from typing import Any, Dict

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


class ContextSummarizer(LLMNodeExecutor):
    node_type = NodeType.ContextSummarizer
    llm_task = LLMTaskType.MEMORY_CONTENT_SUMMARIZE
    prompt_intent = PromptIntent.MEMORY_CONTENT_SUMMARIZE
    resolve_prompt_passes_node_type = True
    include_available_tools = False
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        ...
