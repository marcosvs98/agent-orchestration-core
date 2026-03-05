from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.trace import TraceContext
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.inference_cache import InferenceLayerPolicy
from domain.llm.schemas.llm import InferenceLayer, LLMRequest, LLMResult
from domain.llm.services.llm_executor import LLMExecutor
from domain.llm.services.semantic_cache_service import SemanticCacheService
from domain.llm.exceptions.llm_exceptions import SLMInferenceTimeoutException

class LayeredInferenceOrchestrator(LLMExecutorPort):
    def __init__(
        self,
        *,
        llm_executor: LLMExecutor,
        cache_service: SemanticCacheService | None,
        tracer: RuntimeTracerPort,
        policy: InferenceLayerPolicy | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.cache_service = cache_service
        self.tracer = tracer
        self.policy = policy or InferenceLayerPolicy()

    async def execute_llm(
        self,
        *,
        request: LLMRequest,
        trace: TraceContext,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None = None,
        provider: str = "OPENAI",
        policy_llm: Dict[str, Any] | None = None,
    ) -> LLMResult:
        layer_policy = self._resolve_layer_policy(policy_llm)
        user_query = request.user_message or request.prompt
        task_type_value = request.task_type.value if request.task_type else None
        query_embedding: list[float] | None = None

        with self.tracer.observe(
            as_type="agent",
            name="domain.llm.layered_inference.execute_llm",
            input={
                "tenant_id": str(tenant_id),
                "provider": provider,
                "task_type": task_type_value,
                "cache_enabled": layer_policy.cache_enabled,
                "slm_enabled": layer_policy.slm_enabled,
            },
        ) as agent_handle:
            if (
                layer_policy.cache_enabled
                and user_query
                and task_type_value
                and self.cache_service is not None
            ):
                cache_result = await self.cache_service.lookup(
                    tenant_id=tenant_id,
                    task_type=task_type_value,
                    user_query=user_query,
                    similarity_threshold=layer_policy.cache_similarity_threshold,
                )
                query_embedding = cache_result.query_embedding
                if cache_result.hit and cache_result.entry:
                    result = LLMResult(
                        output=cache_result.entry.response,
                        token_usage={},
                        cost_usd=0.0,
                        latency_ms=0,
                        model_alias=cache_result.entry.model_alias,
                        raw_output={},
                        inference_layer=InferenceLayer.CACHE,
                    )
                    if agent_handle:
                        agent_handle.success(output={"inference_layer": "CACHE"})
                    return result

            result: LLMResult | None = None
            inference_layer = InferenceLayer.LLM

            slm_eligible = (
                layer_policy.slm_enabled
                and task_type_value is not None
                and task_type_value in layer_policy.slm_eligible_tasks
            )

            if slm_eligible:
                slm_request = request.model_copy(
                    update={"model_alias": layer_policy.slm_model_alias}
                )
                try:
                    result = await self.llm_executor.execute_llm(
                        request=slm_request,
                        trace=trace,
                        tenant_id=tenant_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        node_id=node_id,
                        provider=layer_policy.slm_provider,
                        policy_llm=policy_llm,
                    )
                    inference_layer = InferenceLayer.SLM
                except Exception:
                    result = None

                if (
                    result is not None
                    and layer_policy.escalation_on_schema_mismatch
                    and not self._passes_confidence_gate(result=result, request=request)
                ):
                    result = None

            if result is None:
                result = await self.llm_executor.execute_llm(
                    request=request,
                    trace=trace,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=node_id,
                    provider=provider,
                    policy_llm=policy_llm,
                )
                inference_layer = InferenceLayer.LLM

            result = result.model_copy(update={"inference_layer": inference_layer})

            if (
                self.cache_service is not None
                and layer_policy.cache_enabled
                and user_query
                and task_type_value
                and result.output
            ):
                await self.cache_service.persist(
                    tenant_id=tenant_id,
                    task_type=task_type_value,
                    user_query=user_query,
                    query_embedding=query_embedding,
                    response=result.output,
                    model_alias=result.model_alias,
                    inference_layer=inference_layer.value,
                    ttl_seconds=layer_policy.cache_ttl_seconds,
                )

            if agent_handle:
                agent_handle.success(output={"inference_layer": inference_layer.value})
            return result

    def _resolve_layer_policy(
        self, policy_llm: Dict[str, Any] | None
    ) -> InferenceLayerPolicy:
        if policy_llm is None:
            return self.policy
        raw_layer_policy = policy_llm.get("inference_layers")
        if raw_layer_policy is None:
            return self.policy
        try:
            return InferenceLayerPolicy.model_validate(raw_layer_policy)
        except Exception:
            return self.policy

    def _passes_confidence_gate(self, *, result: LLMResult, request: LLMRequest) -> bool:
        if not result.output:
            return False
        if not request.output_schema:
            return True
        schema = request.output_schema
        if isinstance(schema.get("required"), list):
            expected_keys = list(schema["required"])
        else:
            expected_keys = list(schema.get("properties", {}).keys())
        for key in expected_keys:
            if key not in result.output:
                return False
        return True
