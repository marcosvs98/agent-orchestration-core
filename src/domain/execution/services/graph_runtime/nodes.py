from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from domain.execution.services.graph_runtime.types import ExecutionContext, NodeExecutor, NodeResult
from domain.execution.schemas.trace import TraceContext
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMRequest, LLMTaskType
from exceptions.service_exceptions import DomainValidationException


def _payload_from_config(config: Dict[str, Any] | None, default: Dict[str, Any]) -> Dict[str, Any]:
    if config is None:
        return default
    return config.get("output", default) or default


class IntentToolSelectionNode(NodeExecutor):
    node_type = "IntentToolSelectionNode"
    side_effect = False
    deterministic = False

    def __init__(self, llm_executor: LLMExecutorPort | None = None) -> None:
        self.llm_executor = llm_executor

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Select intent deterministically or via LLM executor when configured."""
        config = config or {}
        llm_cfg = config.get("llm")
        if llm_cfg and self.llm_executor:
            task_type_raw = llm_cfg.get("task_type")
            if task_type_raw is None:
                raise DomainValidationException(message="llm_task_type_required")
            try:
                task_type = LLMTaskType(task_type_raw)
            except ValueError as exc:
                raise DomainValidationException(message="llm_task_type_invalid") from exc
            runtime_policy = (context.metadata or {}).get("runtime_policy", {}) if context.metadata else {}
            llm_policy = runtime_policy.get("llm", {})
            provider = llm_cfg.get("provider") or "OPENAI"
            model_alias = llm_policy.get("model_alias") or llm_cfg.get("model_alias")
            if not model_alias:
                raise DomainValidationException(message="llm_model_alias_required")
            request = LLMRequest(
                task_type=task_type,
                input_payload=llm_cfg.get("input", {}),
                input_schema=llm_cfg.get("input_schema", {}),
                output_schema=llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
                max_tokens=llm_policy.get("max_tokens"),
                max_latency_ms=llm_policy.get("max_latency_ms"),
                max_cost_usd=llm_policy.get("max_cost_usd"),
                retry_limit=llm_policy.get("retry_limit"),
                fallback_model_alias=llm_policy.get("fallback_model_alias"),
            )
            try:
                node_uuid: UUID | None = UUID(context.current_node_id)
            except Exception:  # noqa: BLE001
                node_uuid = None
            result = await self.llm_executor.execute_llm(
                request=request,
                trace=TraceContext(
                    trace_id=context.trace_id or UUID(int=0),
                    flow_run_id=context.flow_run_id,
                    tenant_id=context.tenant_id,
                ),
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=node_uuid,
                provider=provider,
                policy_llm=llm_policy,
            )
            return NodeResult(status="SUCCESS", payload=result.output, metrics=result.token_usage)
        payload = _payload_from_config(config, {"validation_status": "VALID", "confidence": 1.0})
        return NodeResult(status="SUCCESS", payload=payload)


class ToolExecutionNode(NodeExecutor):
    node_type = "ToolExecutionNode"
    side_effect = True
    deterministic = False

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Execute tool deterministically with configured output."""
        payload = _payload_from_config(config, {"execution_status": "SUCCESS"})
        status = "SUCCESS" if payload.get("execution_status") == "SUCCESS" else "ERROR"
        return NodeResult(status=status, payload=payload)


class ClarificationNode(NodeExecutor):
    node_type = "ClarificationNode"
    side_effect = False
    deterministic = True

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Request missing inputs."""
        payload = _payload_from_config(config, {"missing_fields": [], "user_message": ""})
        return NodeResult(status="NEEDS_INPUT", payload=payload)


class ResponseNode(NodeExecutor):
    node_type = "ResponseNode"
    side_effect = False
    deterministic = True

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Return final response payload."""
        payload = _payload_from_config(config, {"message": "ok", "payload": {}})
        return NodeResult(status="SUCCESS", payload=payload)


class FallbackNode(NodeExecutor):
    node_type = "FallbackNode"
    side_effect = False
    deterministic = True

    async def execute(self, context: ExecutionContext, config: Dict[str, Any] | None = None) -> NodeResult:
        """Return fallback payload."""
        payload = _payload_from_config(config, {"reason": "fallback", "message": "fallback"})
        return NodeResult(status="SUCCESS", payload=payload)
