"""Smoke tests for intent classifier node metadata (runtime graph uses LLM path)."""

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.nodes.intent_classifier import IntentClassifier
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent


def test_intent_classifier_exposes_node_and_task_binding() -> None:
    assert IntentClassifier.node_type == NodeType.IntentClassifier
    assert IntentClassifier.llm_task == LLMTaskType.INTENT_SELECTION
    assert IntentClassifier.prompt_intent == PromptIntent.INTENT_TOOL_SELECTION
    assert IntentClassifier.resolve_prompt_passes_node_type is True
    assert IntentClassifier.include_available_tools is False
    assert IntentClassifier.result_status == NodeExecutionStatus.SUCCESS
    assert IntentClassifier.state_key_use_value is False


def test_intent_classifier_is_an_llm_node_executor() -> None:
    assert issubclass(IntentClassifier, LLMNodeExecutor)
    assert IntentClassifier.execute is LLMNodeExecutor.execute
