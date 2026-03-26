from __future__ import annotations


from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType


class IntentClassifier:
    node_type = NodeType.IntentClassifier
    llm_task = LLMTaskType.INTENT_SELECTION
    prompt_intent = LLMTaskType.INTENT_SELECTION
    resolve_prompt_passes_node_type = False
    include_available_tools = False
    state_key_use_value = False
