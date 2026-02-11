from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.guardrails import GuardrailDecision, GuardrailDecisionType
from domain.llm.services.cost_engine import CostEngine
from exceptions.service_exceptions import DomainValidationException


class GuardrailEngine:
    def __init__(
        self,
        tracer: RuntimeTracerPort,
        redis_adapter: RedisAdapter,
        cost_engine: CostEngine | None = None,
    ) -> None:
        self.redis = redis_adapter
        self.cost_engine = cost_engine
        self.tracer = tracer

    @staticmethod
    def _flow_cost_key(flow_run_id: UUID) -> str:
        return f"cost:flow_run:{flow_run_id}"

    @staticmethod
    def _tenant_cost_key(tenant_id: UUID) -> str:
        return f"cost:tenant:{tenant_id}"

    @staticmethod
    def _flow_calls_key(flow_run_id: UUID) -> str:
        return f"llm_calls:flow_run:{flow_run_id}"

    @staticmethod
    def _tenant_calls_key(tenant_id: UUID) -> str:
        return f"llm_calls:tenant:{tenant_id}"

    async def _get_cost(self, key: str) -> float:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.guardrail_engine.get_cost",
            input={"key": key},
        ) as retriever_handle:
            data = await self.redis.get(key) or {}
            try:
                cost = float(data.get("usd", 0))
            except (TypeError, ValueError):
                cost = 0.0
            if retriever_handle:
                retriever_handle.success(output={"key": key, "cost": cost})
            return cost

    async def _set_cost(self, key: str, value: float, ttl: int | None = None) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.guardrail_engine.set_cost",
            input={"key": key},
        ) as tool_handle:
            await self.redis.set(key, {"usd": value}, ttl=ttl or 0)
            if tool_handle:
                tool_handle.success(output={"key": key, "value": value})

    async def check_and_reserve(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID,
        request: Any,
        policy_llm: Dict[str, Any],
        provider: str,
        provider_model: str,
    ) -> GuardrailDecision:
        with self.tracer.observe(
            as_type="guardrail",
            name="domain.execution.guardrail_engine.check_and_reserve",
            input={
                "tenant_id": str(tenant_id),
                "flow_run_id": str(flow_run_id),
                "provider": provider,
                "provider_model": provider_model,
            },
        ):
            return await self._check_and_reserve_impl(
                tenant_id=tenant_id,
                flow_run_id=flow_run_id,
                request=request,
                policy_llm=policy_llm,
                provider=provider,
                provider_model=provider_model,
            )

    async def _check_and_reserve_impl(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID,
        request: Any,
        policy_llm: Dict[str, Any],
        provider: str,
        provider_model: str,
    ) -> GuardrailDecision:
        applied_limits: Dict[str, Any] = {}
        overrides: Dict[str, Any] = {}

        max_cost_flow = policy_llm.get("max_cost_usd_per_flow_run")
        max_cost_tenant = policy_llm.get("max_cost_usd_per_tenant_window")
        policy_llm.get("tenant_cost_window_seconds", 3600)
        max_calls_flow = policy_llm.get("max_llm_calls_per_flow_run")
        max_calls_tenant = policy_llm.get("max_llm_calls_per_tenant_window")
        tenant_calls_ttl = policy_llm.get("tenant_llm_calls_window_seconds", 3600)
        max_latency_ms_hard = policy_llm.get("max_latency_ms_hard")
        degrade_model_alias = policy_llm.get("degrade_model_alias")

        estimated_cost = await self._estimate_cost(
            provider, provider_model, request, policy_llm
        )
        flow_cost_key = self._flow_cost_key(flow_run_id)
        tenant_cost_key = self._tenant_cost_key(tenant_id)
        current_flow_cost = await self._get_cost(flow_cost_key)
        current_tenant_cost = await self._get_cost(tenant_cost_key)

        # Rate limits
        flow_calls_key = self._flow_calls_key(flow_run_id)
        tenant_calls_key = self._tenant_calls_key(tenant_id)
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.guardrail_engine.incr_flow_calls",
            input={"key": flow_calls_key},
        ) as tool_handle:
            flow_calls = await self.redis.incr_with_ttl(
                flow_calls_key, ttl=tenant_calls_ttl
            )
            if tool_handle:
                tool_handle.success(output={"flow_calls": flow_calls})
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.guardrail_engine.incr_tenant_calls",
            input={"key": tenant_calls_key},
        ) as tool_handle:
            tenant_calls = await self.redis.incr_with_ttl(
                tenant_calls_key, ttl=tenant_calls_ttl
            )
            if tool_handle:
                tool_handle.success(output={"tenant_calls": tenant_calls})
        if max_calls_flow is not None and flow_calls > int(max_calls_flow):
            return GuardrailDecision(
                decision=GuardrailDecisionType.BLOCK,
                reason_code="RATE_LIMIT_FLOW_RUN",
                applied_limits={
                    "max_llm_calls_per_flow_run": max_calls_flow,
                    "current_calls": flow_calls,
                },
                overrides=overrides,
            )
        if max_calls_tenant is not None and tenant_calls > int(max_calls_tenant):
            return GuardrailDecision(
                decision=GuardrailDecisionType.BLOCK,
                reason_code="RATE_LIMIT_TENANT",
                applied_limits={
                    "max_llm_calls_per_tenant_window": max_calls_tenant,
                    "current_calls": tenant_calls,
                },
                overrides=overrides,
            )

        # Cost guardrails
        projected_flow_cost = current_flow_cost + (estimated_cost or 0)
        projected_tenant_cost = current_tenant_cost + (estimated_cost or 0)
        if max_cost_flow is not None and projected_flow_cost > float(max_cost_flow):
            if degrade_model_alias:
                overrides["model_alias"] = degrade_model_alias
                applied_limits["max_cost_usd_per_flow_run"] = max_cost_flow
                return GuardrailDecision(
                    decision=GuardrailDecisionType.DEGRADE,
                    reason_code="COST_LIMIT_FLOW_RUN",
                    applied_limits=applied_limits,
                    overrides=overrides,
                )
            return GuardrailDecision(
                decision=GuardrailDecisionType.BLOCK,
                reason_code="COST_LIMIT_FLOW_RUN",
                applied_limits={
                    "max_cost_usd_per_flow_run": max_cost_flow,
                    "projected_cost": projected_flow_cost,
                },
                overrides=overrides,
            )
        if max_cost_tenant is not None and projected_tenant_cost > float(
            max_cost_tenant
        ):
            if degrade_model_alias:
                overrides["model_alias"] = degrade_model_alias
                applied_limits["max_cost_usd_per_tenant_window"] = max_cost_tenant
                return GuardrailDecision(
                    decision=GuardrailDecisionType.DEGRADE,
                    reason_code="COST_LIMIT_TENANT",
                    applied_limits=applied_limits,
                    overrides=overrides,
                )
            return GuardrailDecision(
                decision=GuardrailDecisionType.BLOCK,
                reason_code="COST_LIMIT_TENANT",
                applied_limits={
                    "max_cost_usd_per_tenant_window": max_cost_tenant,
                    "projected_cost": projected_tenant_cost,
                },
                overrides=overrides,
            )

        if (
            max_latency_ms_hard is not None
            and request.max_latency_ms
            and request.max_latency_ms > max_latency_ms_hard
        ):
            overrides["max_latency_ms"] = max_latency_ms_hard
            applied_limits["max_latency_ms_hard"] = max_latency_ms_hard

        return GuardrailDecision(
            decision=GuardrailDecisionType.ALLOW,
            reason_code="ALLOW",
            applied_limits=applied_limits,
            overrides=overrides,
        )

    async def record_post_call_cost(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID,
        cost_usd: float | None,
        policy_llm: Dict[str, Any],
    ) -> None:
        if cost_usd is None:
            return
        flow_cost_key = self._flow_cost_key(flow_run_id)
        tenant_cost_key = self._tenant_cost_key(tenant_id)
        tenant_cost_ttl = policy_llm.get("tenant_cost_window_seconds") or 3600
        flow_cost = await self._get_cost(flow_cost_key)
        tenant_cost = await self._get_cost(tenant_cost_key)
        await self._set_cost(flow_cost_key, flow_cost + cost_usd, ttl=tenant_cost_ttl)
        await self._set_cost(
            tenant_cost_key, tenant_cost + cost_usd, ttl=tenant_cost_ttl
        )

    async def _estimate_cost(
        self,
        provider: str,
        provider_model: str,
        request: Any,
        policy_llm: Dict[str, Any],
    ) -> float | None:
        if self.cost_engine is None:
            return None
        max_tokens = request.max_tokens or policy_llm.get("max_tokens") or 0
        if max_tokens == 0:
            return None
        token_usage = {"input_tokens": max_tokens, "output_tokens": max_tokens}
        try:
            return await self.cost_engine.compute_cost(
                provider=provider,
                provider_model=provider_model,
                token_usage=token_usage,
            )
        except DomainValidationException:
            return None
