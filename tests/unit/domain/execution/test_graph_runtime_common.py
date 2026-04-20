"""Coverage for graph_runtime.nodes._common helpers."""

from __future__ import annotations

from uuid import uuid4

from domain.execution.services.graph_runtime.nodes._common import (
    conversation_key_and_stateless,
    read_user_input,
)
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType


def test_conversation_key_default_uses_policy_task_list() -> None:
    key, stateless = conversation_key_and_stateless(
        LLMTaskType.RESPONSE_RENDER,
        {"history_enabled_tasks": ["response_render"]},
        "t1",
        "s1",
        use_history_override=None,
    )
    assert key == "t1:s1"
    assert stateless is False


def test_conversation_key_respects_history_override_false() -> None:
    key, stateless = conversation_key_and_stateless(
        LLMTaskType.RESPONSE_RENDER,
        {"history_enabled_tasks": ["response_render"]},
        "t1",
        "s1",
        use_history_override=False,
    )
    assert key is None
    assert stateless is True


def test_read_user_input_non_dict_payload() -> None:
    ctx = ExecutionContext.model_validate(
        {
            "tenant_id": uuid4(),
            "interaction_id": uuid4(),
            "user_id": "u",
            "session_id": uuid4(),
            "input_payload": None,
            "flow_id": uuid4(),
            "flow_version_id": uuid4(),
            "flow_run_id": uuid4(),
            "correlation_id": uuid4(),
            "current_node_id": "n1",
        }
    )
    assert read_user_input(ctx) == ""


def test_read_user_input_non_string_user_input() -> None:
    ctx = ExecutionContext.model_validate(
        {
            "tenant_id": uuid4(),
            "interaction_id": uuid4(),
            "user_id": "u",
            "session_id": uuid4(),
            "input_payload": {"user_input": 123},
            "flow_id": uuid4(),
            "flow_version_id": uuid4(),
            "flow_run_id": uuid4(),
            "correlation_id": uuid4(),
            "current_node_id": "n1",
        }
    )
    assert read_user_input(ctx) == ""
