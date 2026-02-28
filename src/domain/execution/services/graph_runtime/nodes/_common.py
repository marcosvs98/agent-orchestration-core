from __future__ import annotations

from typing import Any, Dict

from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType


def conversation_key_and_stateless(
    task_type: LLMTaskType | None,
    llm_policy: Dict[str, Any],
    tenant_id: str,
    session_id: str,
) -> tuple[str | None, bool]:
    history_enabled_tasks = llm_policy.get("history_enabled_tasks", ["RESPONSE_RENDER"])
    enabled = bool(task_type and task_type.value in history_enabled_tasks)
    key = f"{tenant_id}:{session_id}" if enabled else None
    return key, not enabled


def read_user_input(context: ExecutionContext) -> str:
    if not isinstance(context.input_payload, dict):
        return ""
    user_input = context.input_payload.get("user_input")
    return user_input if isinstance(user_input, str) else ""
