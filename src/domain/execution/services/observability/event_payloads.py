from typing import Any, Dict, Iterable, List, Mapping
from uuid import UUID


def _as_str_list(values: Iterable[Any]) -> List[str]:
    return [str(v) for v in values]


def build_flow_started_payload(
    flow_id: UUID,
    flow_version_id: UUID,
    snapshot_id: UUID,
    tenant_id: UUID,
) -> Dict[str, Any]:
    return {
        "flow_id": str(flow_id),
        "flow_version_id": str(flow_version_id),
        "snapshot_id": str(snapshot_id),
        "tenant_id": str(tenant_id),
    }


def build_node_started_payload(node_type: str, input_keys: Iterable[str]) -> Dict[str, Any]:
    return {
        "node_type": node_type,
        "input_keys": list(input_keys),
    }


def build_node_completed_payload(
    node_type: str,
    output_keys: Iterable[str],
    status: str,
) -> Dict[str, Any]:
    return {
        "node_type": node_type,
        "output_keys": list(output_keys),
        "status": status,
    }


def build_edge_evaluated_payload(
    expression: str,
    resolved_values: Mapping[str, Any],
    result: bool,
) -> Dict[str, Any]:
    sanitized_values: Dict[str, Any] = {}
    for key, value in resolved_values.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized_values[key] = value
        else:
            sanitized_values[key] = str(value)
    return {
        "expression": expression,
        "resolved_values": sanitized_values,
        "result": result,
    }


def build_flow_failed_payload(failure_reason: str, details: Mapping[str, Any]) -> Dict[str, Any]:
    sanitized_details: Dict[str, Any] = {}
    for key, value in details.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized_details[key] = value
        elif isinstance(value, (list, tuple, set)):
            sanitized_details[key] = _as_str_list(value)
        else:
            sanitized_details[key] = str(value)
    return {
        "failure_reason": failure_reason,
        "details": sanitized_details,
    }


def build_llm_call_started_payload(
    task_type: str,
    model_alias: str,
    provider_model: str,
    provider: str,
    trace_id: str | None,
) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "provider": provider,
        "trace_id": trace_id,
    }


def build_llm_call_completed_payload(
    task_type: str,
    model_alias: str,
    provider_model: str,
    provider: str,
    token_usage: Mapping[str, Any] | None,
    cost_usd: float | None,
    latency_ms: int | None,
    trace_id: str | None,
) -> Dict[str, Any]:
    sanitized_usage: Dict[str, Any] = {}
    for key, value in (token_usage or {}).items():
        if isinstance(value, (int, float)) or value is None:
            sanitized_usage[key] = value
        else:
            sanitized_usage[key] = None
    return {
        "task_type": task_type,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "provider": provider,
        "token_usage": sanitized_usage,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "trace_id": trace_id,
    }


def build_llm_call_failed_payload(
    task_type: str,
    model_alias: str,
    provider_model: str,
    provider: str,
    error_class: str,
    message: str | None,
    trace_id: str | None,
) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "provider": provider,
        "error_class": error_class,
        "message": message,
        "trace_id": trace_id,
    }


def build_guardrail_checked_payload(
    *,
    guardrail_type: str,
    decision: str,
    limit: str,
    current_value: float | int | None,
    estimated_cost_usd: float | None,
    provider: str | None,
    model_alias: str | None,
    provider_model: str | None,
    trace_id: str | None,
) -> Dict[str, Any]:
    return {
        "guardrail_type": guardrail_type,
        "decision": decision,
        "limit": limit,
        "current_value": current_value,
        "estimated_cost_usd": estimated_cost_usd,
        "provider": provider,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "trace_id": trace_id,
    }


def build_guardrail_blocked_payload(
    *,
    guardrail_type: str,
    limit: str,
    current_value: float | int | None,
    reason_code: str,
    provider: str | None,
    model_alias: str | None,
    provider_model: str | None,
    trace_id: str | None,
) -> Dict[str, Any]:
    return {
        "guardrail_type": guardrail_type,
        "limit": limit,
        "current_value": current_value,
        "reason_code": reason_code,
        "provider": provider,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "trace_id": trace_id,
    }


def build_guardrail_degraded_payload(
    *,
    guardrail_type: str,
    limit: str,
    current_value: float | int | None,
    reason_code: str,
    overrides: Mapping[str, Any],
    provider: str | None,
    model_alias: str | None,
    provider_model: str | None,
    trace_id: str | None,
) -> Dict[str, Any]:
    sanitized_overrides: Dict[str, Any] = {}
    for key, value in overrides.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized_overrides[key] = value
        else:
            sanitized_overrides[key] = str(value)
    return {
        "guardrail_type": guardrail_type,
        "limit": limit,
        "current_value": current_value,
        "reason_code": reason_code,
        "overrides": sanitized_overrides,
        "provider": provider,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "trace_id": trace_id,
    }
