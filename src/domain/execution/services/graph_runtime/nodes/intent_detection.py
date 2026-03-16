from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.ports.runtime_tracer import ObservationHandle, RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes.intent_detection_llm_fallback import (
    IntentDetectionLLMFallback,
)
from domain.execution.services.graph_runtime.nodes.intent_examples_retriever import (
    IntentExamplesRetriever,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    IntentClassificationMode,
    IntentClassificationReason,
    IntentType,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType

DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_TOP_K = 1


class IntentDetectionNode:
    node_type = NodeType.IntentDetectionNode
    side_effect = False
    deterministic = False

    def __init__(
        self,
        *,
        tracer: RuntimeTracerPort,
        agents_repository: AgentsRepository | None,
        intent_examples_retriever: IntentExamplesRetriever | None,
        llm_fallback: IntentDetectionLLMFallback | None = None,
    ) -> None:
        self.tracer = tracer
        self.agents_repository = agents_repository
        self.intent_examples_retriever = intent_examples_retriever
        self.llm_fallback = llm_fallback

    async def execute(
        self, context: ExecutionContext, config: dict[str, Any] | None = None
    ) -> NodeResult:
        cfg = config or {}
        confidence_threshold = self._config_float(
            cfg, "confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD
        )
        top_k = self._config_int(cfg, "top_k", DEFAULT_TOP_K)
        user_input = str((context.input_payload or {}).get("user_input", "") or "")

        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.intent_detection.execute",
            input={
                "tenant_id": str(context.tenant_id),
                "node_id": str(context.current_node_id),
                "user_input_length": len(user_input),
                "confidence_threshold": confidence_threshold,
                "top_k": top_k,
            },
        ) as execution_handle:
            if not user_input.strip():
                result = self._build_result(
                    intent_type=IntentType.CONVERSATION,
                    confidence=1.0,
                    context=context,
                )
                self._report_success(
                    execution_handle,
                    result,
                    IntentClassificationMode.HEURISTIC,
                    IntentClassificationReason.EMPTY_USER_INPUT,
                    confidence_threshold=confidence_threshold,
                    top_k=top_k,
                )
                return result

            rag_config_id = await self._resolve_rag_config_id(context)
            if rag_config_id and self.intent_examples_retriever:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.execution.nodes.intent_detection.semantic_classification",
                    input={
                        "tenant_id": str(context.tenant_id),
                        "rag_config_id": str(rag_config_id),
                        "top_k": top_k,
                    },
                ) as classification_handle:
                    semantic_match = (
                        await self.intent_examples_retriever.retrieve_best_match(
                            tenant_id=context.tenant_id,
                            rag_config_id=rag_config_id,
                            user_input=user_input,
                            top_k=top_k,
                        )
                    )
                    if classification_handle:
                        classification_handle.success(
                            output={
                                "matched_intent_type": (
                                    semantic_match.intent_type.value
                                    if semantic_match
                                    else None
                                ),
                                "matched_score": (
                                    semantic_match.score if semantic_match else None
                                ),
                            }
                        )
                if semantic_match and semantic_match.score >= confidence_threshold:
                    result = self._build_result(
                        intent_type=semantic_match.intent_type,
                        confidence=semantic_match.score,
                        context=context,
                    )
                    self._report_success(
                        execution_handle,
                        result,
                        IntentClassificationMode.SEMANTIC,
                        IntentClassificationReason.ABOVE_CONFIDENCE_THRESHOLD,
                        confidence_threshold=confidence_threshold,
                        semantic_score=semantic_match.score,
                        top_k=top_k,
                    )
                    return result
                fallback_reason = (
                    IntentClassificationReason.BELOW_CONFIDENCE_THRESHOLD
                    if semantic_match
                    else IntentClassificationReason.NO_SEMANTIC_MATCH
                )
                llm_result = await self._execute_llm_fallback(
                    context=context,
                    config=config,
                    execution_handle=execution_handle,
                    reason=fallback_reason,
                    confidence_threshold=confidence_threshold,
                    semantic_score=semantic_match.score if semantic_match else None,
                    top_k=top_k,
                )
                if llm_result is not None:
                    return llm_result
                result = self._build_result(
                    intent_type=IntentType.CONVERSATION,
                    confidence=semantic_match.score if semantic_match else 0.0,
                    context=context,
                )
                self._report_success(
                    execution_handle,
                    result,
                    IntentClassificationMode.DEFAULT,
                    IntentClassificationReason.LLM_FALLBACK_UNAVAILABLE,
                    confidence_threshold=confidence_threshold,
                    semantic_score=semantic_match.score if semantic_match else None,
                    top_k=top_k,
                )
                return result

            llm_result = await self._execute_llm_fallback(
                context=context,
                config=config,
                execution_handle=execution_handle,
                reason=IntentClassificationReason.RAG_CONFIG_NOT_FOUND,
                confidence_threshold=confidence_threshold,
                semantic_score=None,
                top_k=top_k,
            )
            if llm_result is not None:
                return llm_result
            result = self._build_result(
                intent_type=IntentType.CONVERSATION,
                confidence=0.0,
                context=context,
            )
            self._report_success(
                execution_handle,
                result,
                IntentClassificationMode.DEFAULT,
                IntentClassificationReason.LLM_FALLBACK_UNAVAILABLE,
                confidence_threshold=confidence_threshold,
                top_k=top_k,
            )
            return result

    async def _execute_llm_fallback(
        self,
        *,
        context: ExecutionContext,
        config: dict[str, Any] | None,
        execution_handle: ObservationHandle | None,
        reason: IntentClassificationReason,
        confidence_threshold: float,
        semantic_score: float | None,
        top_k: int,
    ) -> NodeResult | None:
        if self.llm_fallback is None:
            return None
        llm_result = await self.llm_fallback.execute(context, config)
        self._report_success(
            execution_handle,
            llm_result,
            IntentClassificationMode.LLM_FALLBACK,
            reason,
            confidence_threshold=confidence_threshold,
            semantic_score=semantic_score,
            top_k=top_k,
        )
        return llm_result

    def _build_result(
        self,
        *,
        intent_type: IntentType,
        confidence: float,
        context: ExecutionContext,
    ) -> NodeResult:
        output = {
            "result": [
                {
                    "intent_type": intent_type.value,
                    "confidence": confidence,
                    "priority": 1,
                }
            ],
            "overall_confidence": confidence,
        }
        next_state = {**(context.state or {}), self.node_type: output}
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=output,
            next_state=next_state,
        )

    def _report_success(
        self,
        handle: ObservationHandle | None,
        result: NodeResult,
        mode: IntentClassificationMode,
        reason: IntentClassificationReason,
        *,
        confidence_threshold: float,
        top_k: int,
        semantic_score: float | None = None,
    ) -> None:
        output: dict[str, Any] = {
            "classification_mode": mode.value,
            "reason": reason.value,
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "selected_intent_type": self._extract_intent_type(result),
            "overall_confidence": self._extract_overall_confidence(result),
        }
        if semantic_score is not None:
            output["semantic_score"] = semantic_score
        if handle:
            handle.success(output=output)

    async def _resolve_rag_config_id(self, context: ExecutionContext) -> UUID | None:
        if self.agents_repository is None:
            return None
        try:
            node_id = UUID(context.current_node_id)
        except (ValueError, TypeError):
            return None
        agent_version_id = await self.agents_repository.get_agent_version_id_by_node_id(
            node_id
        )
        if not agent_version_id:
            return None
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            return None
        return agent_version.rag_config_id

    @staticmethod
    def _config_float(config: dict[str, Any], key: str, default: float) -> float:
        raw = config.get(key)
        if raw is None:
            return default
        if isinstance(raw, (int, float)):
            return float(raw)
        return default

    @staticmethod
    def _config_int(config: dict[str, Any], key: str, default: int) -> int:
        raw = config.get(key)
        if raw is None:
            return default
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        return default

    @staticmethod
    def _extract_intent_type(result: NodeResult) -> str | None:
        data = result.data if isinstance(result.data, dict) else {}
        rows = data.get("result")
        if not isinstance(rows, list) or not rows:
            return None
        first = rows[0]
        if not isinstance(first, dict):
            return None
        intent_type = first.get("intent_type")
        if not isinstance(intent_type, str):
            return None
        return intent_type

    @staticmethod
    def _extract_overall_confidence(result: NodeResult) -> float | None:
        data = result.data if isinstance(result.data, dict) else {}
        overall_confidence = data.get("overall_confidence")
        if isinstance(overall_confidence, (float, int)):
            return float(overall_confidence)
        return None
