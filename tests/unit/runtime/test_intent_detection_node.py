"""Smoke tests for intent classifier node metadata (runtime graph uses LLM path)."""

from domain.execution.services.graph_runtime.nodes.intent_classifier import IntentClassifier
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType


def test_intent_classifier_exposes_node_and_task_binding() -> None:
    assert IntentClassifier.node_type == NodeType.IntentClassifier
    assert IntentClassifier.llm_task == LLMTaskType.INTENT_SELECTION
    assert IntentClassifier.prompt_intent == LLMTaskType.INTENT_SELECTION
    assert IntentClassifier.resolve_prompt_passes_node_type is False
    assert IntentClassifier.include_available_tools is False
    assert IntentClassifier.state_key_use_value is False
