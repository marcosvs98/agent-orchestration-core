from typing import Any, Dict, List, TypedDict


class FlowStartedPayload(TypedDict):
    flow_id: str
    flow_version_id: str
    snapshot_id: str
    tenant_id: str


class NodeStartedPayload(TypedDict):
    node_type: str
    input_keys: List[str]


class NodeCompletedPayload(TypedDict):
    node_type: str
    output_keys: List[str]
    status: str


class EdgeEvaluatedPayload(TypedDict):
    expression: str
    resolved_values: Dict[str, Any]
    result: bool


class FlowFailedPayload(TypedDict):
    failure_reason: str
    details: Dict[str, Any]


class LLMCallStartedPayload(TypedDict):
    task_type: str
    model_alias: str
    provider_model: str
    provider: str
    trace_id: str | None


class LLMCallCompletedPayload(TypedDict):
    task_type: str
    model_alias: str
    provider_model: str
    provider: str
    token_usage: Dict[str, int | float | None]
    cost_usd: float | None
    latency_ms: int | None
    trace_id: str | None


class LLMCallFailedPayload(TypedDict):
    task_type: str
    model_alias: str
    provider_model: str
    provider: str
    error_class: str
    message: str | None
    trace_id: str | None


class GuardrailCheckedPayload(TypedDict):
    guardrail_type: str
    decision: str
    limit: str
    current_value: float | int | None
    estimated_cost_usd: float | None
    provider: str | None
    model_alias: str | None
    provider_model: str | None
    trace_id: str | None


class GuardrailBlockedPayload(TypedDict):
    guardrail_type: str
    limit: str
    current_value: float | int | None
    reason_code: str
    provider: str | None
    model_alias: str | None
    provider_model: str | None
    trace_id: str | None


class GuardrailDegradedPayload(TypedDict):
    guardrail_type: str
    limit: str
    current_value: float | int | None
    reason_code: str
    overrides: Dict[str, Any]
    provider: str | None
    model_alias: str | None
    provider_model: str | None
    trace_id: str | None


class NodePromptUpdatedPayload(TypedDict):
    prompt_id: str
    node_type: str
    version: int
    frozen_hash: str
    created_by: str


class NodePromptExecutedPayload(TypedDict):
    node_type: str
    prompt_version: int
    frozen_hash: str
    token_usage: Dict[str, int | float | None]
    latency_ms: int | None
    cost_usd: float | None
