from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.tools.schemas.tools import AvailableTool


def _runtime_policy_llm() -> dict[str, Any]:
    return {
        "execution": {"strict_contract_mode": False},
        "limits": {"tool_fanout_max_concurrency": 4},
        "llm": {
            "model_alias": "gpt-4o-mini",
            "max_tokens": 1024,
            "max_latency_ms": 120000,
            "max_cost_usd": 2.0,
            "retry_limit": 0,
        },
    }


def make_base_context(
    *,
    tenant_id: UUID,
    current_node_id: UUID,
    user_input: str,
    user_id: str | None = None,
    state: dict[str, Any] | None = None,
    available_tools: list[AvailableTool] | None = None,
    current_node_run_id: UUID | None = None,
    metadata_extra: dict[str, Any] | None = None,
    flow_run_id: UUID | None = None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    flow_version_id: UUID | None = None,
) -> ExecutionContext:
    md: dict[str, Any] = {"runtime_policy": _runtime_policy_llm()}
    if metadata_extra:
        md = {**md, **metadata_extra}
    return ExecutionContext(
        tenant_id=tenant_id,
        interaction_id=uuid.uuid4(),
        user_id=user_id or f"node_validate_{uuid.uuid4().hex[:10]}",
        session_id=session_id or uuid.uuid4(),
        input_payload={"user_input": user_input},
        flow_id=uuid.uuid4(),
        flow_version_id=flow_version_id or uuid.uuid4(),
        flow_run_id=flow_run_id or uuid.uuid4(),
        correlation_id=correlation_id or uuid.uuid4(),
        trace_id=uuid.uuid4(),
        current_node_id=str(current_node_id),
        current_node_run_id=current_node_run_id,
        state=dict(state or {}),
        available_tools=list(available_tools or []),
        metadata=md,
    )


def llm_node_config() -> dict[str, Any]:
    return {
        "llm": {
            "model_alias": "gpt-4o-mini",
            "max_tokens": 1024,
        }
    }
