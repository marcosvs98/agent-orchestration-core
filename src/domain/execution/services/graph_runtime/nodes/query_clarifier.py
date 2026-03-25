from __future__ import annotations

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


class QueryClarifier(LLMNodeExecutor):
    node_type = NodeType.QueryClarifier
    llm_task = LLMTaskType.CLARIFICATION
    prompt_intent = PromptIntent.CLARIFICATION
    deterministic = True
    resolve_prompt_passes_node_type = False
    include_available_tools = False
    result_status = NodeExecutionStatus.NEEDS_INPUT
    write_next_state = False
    state_key_use_value = False
