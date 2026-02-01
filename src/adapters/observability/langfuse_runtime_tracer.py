from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any, Dict, Iterator
from uuid import UUID

import structlog
from adapters.observability.logging import get_logger
from domain.execution.schemas.trace import TraceContext
from domain.execution.schemas.events import ExecutionEventType
from exceptions.service_exceptions import DomainValidationException
from langfuse import Langfuse, propagate_attributes
from settings import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)

logger = get_logger(__name__)


def _get_contextvars_metadata() -> Dict[str, Any]:
    """Capture structlog contextvars automatically for metadata enrichment."""
    try:
        return structlog.contextvars.get_contextvars()
    except Exception:
        return {}


def _enrich_metadata(
    base_metadata: Dict[str, Any] | None = None,
    environment: str | None = None,
    runtime_version: str | None = None,
) -> Dict[str, Any]:
    """Enrich metadata with contextvars, environment, and runtime_version."""
    metadata = dict(base_metadata) if base_metadata else {}
    contextvars_metadata = _get_contextvars_metadata()
    if contextvars_metadata:
        metadata.update(contextvars_metadata)
    if environment:
        metadata["environment"] = environment
    if runtime_version:
        metadata["runtime_version"] = runtime_version
    return metadata


class GuardrailSpanHandle:
    def __init__(self, guardrail_observation: Any) -> None:
        self.guardrail_observation = guardrail_observation

    def update_decision(
        self,
        *,
        decision: str,
        reason_code: str,
        applied_limits: dict,
        overrides: dict | None = None,
    ) -> None:
        if self.guardrail_observation is None:
            return
        try:
            update_data: Dict[str, Any] = {
                "output": {
                    "decision": decision,
                    "reason_code": reason_code,
                    "applied_limits": applied_limits,
                    "overrides": overrides or {},
                },
                "metadata": {
                    "decision": decision,
                    "reason_code": reason_code,
                },
            }
            if decision == "BLOCK":  # Todo: To use StrEnum
                update_data["level"] = "ERROR"  # Todo: To use StrEnum
                update_data["status_message"] = f"Guardrail blocked: {reason_code}"
            contextvars_metadata = _get_contextvars_metadata()
            if contextvars_metadata:
                update_data["metadata"].update(contextvars_metadata)
            self.guardrail_observation.update(**update_data)
        except Exception as e:
            logger.error(
                "Failed to update guardrail decision in Langfuse",
                error=str(e),
                error_type=type(e).__name__,
            )


class RetrieverSpanHandle:
    def __init__(self, retriever_observation: Any) -> None:
        self.retriever_observation = retriever_observation

    def update(
        self,
        *,
        input: Dict[str, Any] | None = None,
        output: Dict[str, Any] | None = None,
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        if self.retriever_observation is None:
            return
        try:
            update_data: Dict[str, Any] = {}
            if input is not None:
                update_data["input"] = input
            if output is not None:
                update_data["output"] = output
            if usage_details is not None:
                update_data["usage_details"] = usage_details
            if update_data:
                self.retriever_observation.update(**update_data)
        except Exception as e:
            logger.error(
                "Failed to update retriever span in Langfuse",
                error=str(e),
                error_type=type(e).__name__,
            )

    def update_results(
        self,
        *,
        chunks: list,
        top_k: int,
        similarity_scores: list[float],
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        self.update(
            output={
                "chunks": chunks,
                "top_k": top_k,
                "similarity_scores": similarity_scores,
            },
            usage_details=usage_details,
        )


class EvaluatorSpanHandle:
    def __init__(self, evaluator_observation: Any) -> None:
        self.evaluator_observation = evaluator_observation

    def update_result(
        self,
        *,
        passed: bool,
        errors: list[str] | None = None,
        score: float | None = None,
    ) -> None:
        if self.evaluator_observation is None:
            return
        try:
            output: Dict[str, Any] = {"passed": passed}
            if errors is not None:
                output["errors"] = errors
            if score is not None:
                output["score"] = score
            self.evaluator_observation.update(
                output=output, metadata={"passed": passed}
            )
        except Exception as e:
            logger.error(
                "Failed to update evaluator result in Langfuse",
                error=str(e),
                error_type=type(e).__name__,
            )


class EmbeddingSpanHandle:
    def __init__(self, embedding_observation: Any) -> None:
        self.embedding_observation = embedding_observation

    def update_success(
        self,
        *,
        embedding: list[float],
        dimension: int,
        latency_ms: int,
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        if self.embedding_observation is None:
            return
        try:
            update_data: Dict[str, Any] = {
                "output": {
                    "embedding": embedding,
                    "dimension": dimension,
                    "latency_ms": latency_ms,
                },
                "latency": latency_ms / 1000.0,
            }
            if usage_details is not None:
                update_data["usage_details"] = usage_details
            self.embedding_observation.update(**update_data)
        except Exception as e:
            logger.error(
                "Failed to update embedding success in Langfuse",
                error=str(e),
                error_type=type(e).__name__,
            )

    def update_failure(self, *, error_type: str, error_message: str) -> None:
        if self.embedding_observation is None:
            return
        try:
            self.embedding_observation.update(
                level="ERROR",
                status_message=error_message,
                output={
                    "status": "error",
                    "error_type": error_type,
                    "error_message": error_message,
                },
                metadata={"error_type": error_type},
            )
        except Exception as e:
            logger.error(
                "Failed to update embedding failure in Langfuse",
                error=str(e),
                error_type=type(e).__name__,
            )


class LLMGenerationHandle:
    def __init__(self, generation_observation: Any) -> None:
        self.generation_observation = generation_observation
        self.updated = False

    def update_success(
        self,
        *,
        output: dict,
        token_usage: dict,
        cost: float,
        latency_ms: int,
        model_version: str,
        input_data: dict | None = None,
        model_parameters: dict | None = None,
        completion_start_time: datetime | None = None,
    ) -> None:
        if self.generation_observation is None:
            return
        try:
            update_data: Dict[str, Any] = {
                "output": output,
                "usage": token_usage,
                "unit_cost": cost,
                "latency": latency_ms / 1000.0,
                "model": model_version,
            }

            if input_data:
                update_data["input"] = input_data

            if model_parameters:
                update_data["model_parameters"] = model_parameters

            if token_usage:
                update_data["usage_details"] = {
                    "input_tokens": token_usage.get("input_tokens")
                    or token_usage.get("prompt_tokens")
                    or 0,
                    "output_tokens": token_usage.get("output_tokens")
                    or token_usage.get("completion_tokens")
                    or 0,
                    "total_tokens": token_usage.get("total_tokens") or 0,
                }

            if cost:
                update_data["cost_details"] = {
                    "total_cost": cost,
                }

            if completion_start_time:
                update_data["completion_start_time"] = completion_start_time

            contextvars_metadata = _get_contextvars_metadata()
            if contextvars_metadata:
                update_data["metadata"] = {
                    **update_data.get("metadata", {}),
                    **contextvars_metadata,
                }

            self.generation_observation.update(**update_data)
            self.updated = True
        except Exception:
            logger.exception(
                "Failed to update LLM generation success in Langfuse",
            )

    def update_failure(
        self,
        *,
        error_type: str,
        error_message: str,
        input_data: dict | None = None,
        traceback_str: str | None = None,
    ) -> None:
        if self.generation_observation is None:
            return
        try:
            update_data: Dict[str, Any] = {
                "level": "ERROR",
                "status_message": error_message,
                "output": {
                    "status": "error",
                    "error_type": error_type,
                    "error_message": error_message,
                },
            }

            if input_data:
                update_data["input"] = input_data

            if traceback_str:
                update_data["output"]["traceback"] = traceback_str

            metadata = {"error_type": error_type}
            contextvars_metadata = _get_contextvars_metadata()
            if contextvars_metadata:
                metadata.update(contextvars_metadata)
            update_data["metadata"] = metadata

            self.generation_observation.update(**update_data)
            self.updated = True
        except Exception:
            logger.exception(
                "Failed to update LLM generation failure in Langfuse",
            )


class LangfuseRuntimeTracer:
    """Single entry point for Langfuse integration. Blocks execution if misconfigured."""

    def __init__(
        self, *, environment: str | None = None, runtime_version: str | None = None
    ) -> None:
        if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY or not LANGFUSE_HOST:
            raise DomainValidationException(message="langfuse_not_configured")
        self.environment = environment or ENVIRONMENT
        self.runtime_version = runtime_version or APPLICATION_VERSION
        try:
            self.langfuse = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Langfuse client",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DomainValidationException(
                message="langfuse_initialization_failed"
            ) from e
        self._current_flow_span: Any = None
        self._current_trace_context: TraceContext | None = None

    def start_flow_trace(
        self,
        *,
        flow_run_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: UUID | None,
        external_request_id: str | None = None,
        trace_id: UUID | None = None,
    ) -> TraceContext:
        try:
            if external_request_id:
                deterministic_trace_id = self.langfuse.create_trace_id(
                    seed=external_request_id
                )
                trace_id_val = UUID(deterministic_trace_id)
            else:
                trace_id_val = trace_id or flow_run_id

            return TraceContext(
                trace_id=trace_id_val,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                root_observation_id=None,
            )
        except Exception:
            logger.exception("Failed to start flow trace", flow_run_id=str(flow_run_id))
            trace_id_val = trace_id or flow_run_id
            return TraceContext(
                trace_id=trace_id_val,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                root_observation_id=None,
            )

    def end_flow_trace(self, *, output: dict | None = None) -> None:
        try:
            if self._current_flow_span is not None:
                self._current_flow_span.update(output=output or {})
            self.flush()
        except Exception:
            logger.exception("Failed to end flow trace in Langfuse")

    @contextlib.contextmanager
    def start_flow_span(
        self, *, trace: TraceContext, name: str | None = None
    ) -> Iterator[None]:
        self._current_trace_context = trace
        span_name = name or "flow-run"
        try:
            trace_id_hex = trace.trace_id.hex
            base_metadata = {
                "tenant_id": str(trace.tenant_id),
                "flow_run_id": str(trace.flow_run_id),
            }
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="span",
                name=span_name,
                trace_context={"trace_id": trace_id_hex},
                input={
                    "flow_run_id": str(trace.flow_run_id),
                    "tenant_id": str(trace.tenant_id),
                },
                metadata=enriched_metadata,
            ) as flow_span:
                self._current_flow_span = flow_span
                root_observation_id = getattr(flow_span, "id", None) or getattr(
                    flow_span, "observation_id", None
                )
                if root_observation_id and not trace.root_observation_id:
                    object.__setattr__(
                        trace, "root_observation_id", root_observation_id
                    )
                with propagate_attributes(
                    user_id=None,
                    session_id=None,
                    metadata=enriched_metadata,
                    version=self.runtime_version,
                ):
                    yield
        except Exception as e:
            logger.exception(
                "Failed to start flow span in Langfuse",
                error_type=type(e).__name__,
                trace_id=str(trace.trace_id),
            )
            yield
        finally:
            self._current_trace_context = None
            self._current_flow_span = None

    @contextlib.contextmanager
    def start_node_span(
        self,
        *,
        node_id: str,
        node_type: str,
        input: Dict[str, Any],
        name: str | None = None,
    ) -> Iterator[None]:
        span_name = name or "node-execution"
        try:
            base_metadata = {
                "node_id": node_id,
                "node_type": node_type,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="span",
                name=span_name,
                input={
                    "node_id": node_id,
                    "node_type": node_type,
                    "input_keys": list(input.keys()) if isinstance(input, dict) else [],
                },
                metadata=enriched_metadata,
            ) as node_span:
                try:
                    yield
                    node_span.update(
                        output={
                            "node_id": node_id,
                            "node_type": node_type,
                            "status": "completed",
                        }
                    )
                except Exception as inner_exc:
                    try:
                        node_span.update(
                            output={
                                "node_id": node_id,
                                "node_type": node_type,
                                "status": "failed",
                                "error": str(inner_exc)[:200],
                            }
                        )
                    except Exception:
                        pass
                    raise
        except Exception as e:
            logger.exception(
                "Failed to start node span in Langfuse",
                error_type=type(e).__name__,
                node_id=node_id,
                node_type=node_type,
            )
            yield

    @contextlib.contextmanager
    def start_guardrail_span(
        self, *, guardrail_type: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[GuardrailSpanHandle]:
        span_name = name or f"guardrail-{guardrail_type.lower()}"
        try:
            base_metadata = {
                "guardrail_type": guardrail_type,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="guardrail",
                name=span_name,
                input={
                    "guardrail_type": guardrail_type,
                    "input_keys": list(input.keys()) if isinstance(input, dict) else [],
                },
                metadata=enriched_metadata,
            ) as guardrail_span:
                handle = GuardrailSpanHandle(guardrail_span)
                yield handle
        except Exception as e:
            logger.exception(
                "Failed to start guardrail span in Langfuse",
                error_type=type(e).__name__,
                guardrail_type=guardrail_type,
            )
            handle = GuardrailSpanHandle(None)
            yield handle

    @contextlib.contextmanager
    def start_tool_span(
        self, *, tool_id: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        span_name = name or f"tool-{tool_id}"
        try:
            base_metadata = {
                "tool_id": tool_id,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="tool",
                name=span_name,
                input={
                    "tool_id": tool_id,
                    "input_keys": list(input.keys()) if isinstance(input, dict) else [],
                },
                metadata=enriched_metadata,
            ) as tool_span:
                yield
                tool_span.update(output={"tool_id": tool_id, "status": "completed"})
        except Exception as e:
            logger.exception(
                "Failed to start tool span in Langfuse",
                error_type=type(e).__name__,
                tool_id=tool_id,
            )
            yield

    @contextlib.contextmanager
    def start_llm_generation(
        self,
        *,
        model_id: str,
        task_type: str,
        input: Dict[str, Any],
        prompt_version: int | None = None,
        prompt_frozen_hash: str | None = None,
        node_type: str | None = None,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        tenant_id: UUID | None = None,
        name: str | None = None,
    ) -> Iterator[LLMGenerationHandle]:
        span_name = name or "llm-call"
        try:
            base_metadata: Dict[str, Any] = {
                "task_type": task_type,
                "model_id": model_id,
            }
            if prompt_version is not None:
                base_metadata["prompt_version"] = prompt_version
            if prompt_frozen_hash:
                base_metadata["prompt_frozen_hash"] = prompt_frozen_hash
            if node_type:
                base_metadata["node_type"] = node_type
            if tenant_id:
                base_metadata["tenant_id"] = str(tenant_id)
            if self._current_trace_context:
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
                if not tenant_id:
                    base_metadata["tenant_id"] = str(
                        self._current_trace_context.tenant_id
                    )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )

            with self.langfuse.start_as_current_observation(
                as_type="generation",
                name=span_name,
                model=model_id,
                input=input
                if isinstance(input, dict)
                else {
                    "input_keys": list(input.keys()) if isinstance(input, dict) else []
                },
                metadata=enriched_metadata,
            ) as generation:
                propagate_metadata = {
                    "task_type": task_type,
                    "model_id": model_id,
                }
                if tenant_id or (
                    self._current_trace_context
                    and self._current_trace_context.tenant_id
                ):
                    propagate_metadata["tenant_id"] = str(
                        tenant_id
                        or (
                            self._current_trace_context.tenant_id
                            if self._current_trace_context
                            else None
                        )
                    )
                propagate_cm = (
                    propagate_attributes(
                        user_id=str(user_id) if user_id else None,
                        session_id=str(session_id) if session_id else None,
                        metadata=propagate_metadata,
                    )
                    if user_id or session_id or tenant_id or self._current_trace_context
                    else contextlib.nullcontext()
                )
                with propagate_cm:
                    handle = LLMGenerationHandle(generation)
                    try:
                        yield handle
                    except Exception as inner_exc:
                        try:
                            if generation:
                                generation.update(
                                    output={
                                        "status": "failed",
                                        "error": str(inner_exc)[:200],
                                    }
                                )
                        except Exception:
                            pass
                        raise
        except Exception as e:
            logger.exception(
                "Failed to start LLM generation in Langfuse",
                error_type=type(e).__name__,
                model_id=model_id,
                task_type=task_type,
            )
            handle = LLMGenerationHandle(None)
            yield handle

    @contextlib.contextmanager
    def start_retriever_span(
        self,
        *,
        retriever_name: str,
        query: str | None = None,
        input: Dict[str, Any] | None = None,
        name: str | None = None,
    ) -> Iterator[RetrieverSpanHandle]:
        if not self._current_trace_context:
            handle = RetrieverSpanHandle(None)
            yield handle
            return

        span_name = name or f"retriever.{retriever_name}"
        retriever_input = input or {}
        if query:
            retriever_input["query"] = query
        try:
            base_metadata = {
                "retriever_name": retriever_name,
                "tenant_id": str(self._current_trace_context.tenant_id),
                "flow_run_id": str(self._current_trace_context.flow_run_id),
            }
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="retriever",
                name=span_name,
                input=retriever_input,
                metadata=enriched_metadata,
            ) as retriever_span:
                handle = RetrieverSpanHandle(retriever_span)
                yield handle
        except Exception as e:
            logger.exception(
                "Failed to start retriever span in Langfuse",
                error_type=type(e).__name__,
                retriever_name=retriever_name,
            )
            handle = RetrieverSpanHandle(None)
            yield handle

    @contextlib.contextmanager
    def start_evaluator_span(
        self, *, evaluator_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[EvaluatorSpanHandle]:
        span_name = name or f"evaluator.{evaluator_name}"
        try:
            base_metadata = {
                "evaluator_name": evaluator_name,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="evaluator",
                name=span_name,
                input=input,
                metadata=enriched_metadata,
            ) as evaluator_span:
                handle = EvaluatorSpanHandle(evaluator_span)
                try:
                    yield handle
                except Exception as inner_exc:
                    try:
                        if evaluator_span:
                            evaluator_span.update(
                                output={
                                    "status": "failed",
                                    "error": str(inner_exc)[:200],
                                }
                            )
                    except Exception:
                        pass
                    raise
        except Exception as e:
            logger.exception(
                "Failed to start evaluator span in Langfuse",
                error_type=type(e).__name__,
                evaluator_name=evaluator_name,
            )
            handle = EvaluatorSpanHandle(None)
            yield handle

    @contextlib.contextmanager
    def start_chain_span(
        self, *, chain_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        span_name = name or f"chain.{chain_name}"
        try:
            base_metadata = {
                "chain_name": chain_name,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="chain",
                name=span_name,
                input=input,
                metadata=enriched_metadata,
            ) as chain_span:
                yield
                chain_span.update(
                    output={"chain_name": chain_name, "status": "completed"}
                )
        except Exception as e:
            logger.exception(
                "Failed to start chain span in Langfuse",
                error_type=type(e).__name__,
                chain_name=chain_name,
            )
            yield

    @contextlib.contextmanager
    def start_embedding_span(
        self, *, model_id: str, input_text: str, name: str | None = None
    ) -> Iterator[EmbeddingSpanHandle]:
        span_name = name or "embedding-generation"
        try:
            base_metadata = {
                "model_id": model_id,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="embedding",
                name=span_name,
                model=model_id,
                input={"input_text": input_text, "model_id": model_id},
                metadata=enriched_metadata,
            ) as embedding_span:
                handle = EmbeddingSpanHandle(embedding_span)
                yield handle
        except Exception as e:
            logger.exception(
                "Failed to start embedding span in Langfuse",
                error_type=type(e).__name__,
                model_id=model_id,
            )
            handle = EmbeddingSpanHandle(None)
            yield handle

    @contextlib.contextmanager
    def start_agent_span(
        self, *, agent_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        span_name = name or f"agent.{agent_name}"
        try:
            base_metadata = {
                "agent_name": agent_name,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            with self.langfuse.start_as_current_observation(
                as_type="agent",
                name=span_name,
                input=input,
                metadata=enriched_metadata,
            ) as agent_span:
                yield
                agent_span.update(
                    output={"agent_name": agent_name, "status": "completed"}
                )
        except Exception as e:
            logger.exception(
                "Failed to start agent span in Langfuse",
                error_type=type(e).__name__,
                agent_name=agent_name,
            )
            yield

    def create_event(
        self, *, event_type: ExecutionEventType, input: Dict[str, Any] | None = None
    ) -> None:
        event_name = f"event.{event_type.value}"
        try:
            base_metadata = {
                "event_type": event_type.value,
            }
            if self._current_trace_context:
                base_metadata["tenant_id"] = str(self._current_trace_context.tenant_id)
                base_metadata["flow_run_id"] = str(
                    self._current_trace_context.flow_run_id
                )
            enriched_metadata = _enrich_metadata(
                base_metadata, self.environment, self.runtime_version
            )
            self.langfuse.create_event(
                name=event_name,
                input=input or {},
                metadata=enriched_metadata,
            )
        except Exception as e:
            logger.exception(
                "Failed to create event in Langfuse",
                error_type=type(e).__name__,
                event_type=event_type.value,
            )

    def flush(self) -> None:
        try:
            self.langfuse.flush()
        except Exception as e:
            logger.exception(
                "Failed to flush Langfuse events",
                error_type=type(e).__name__,
            )

    def shutdown(self) -> None:
        try:
            self.langfuse.shutdown()
        except Exception as e:
            logger.exception(
                "Failed to shutdown Langfuse client",
                error_type=type(e).__name__,
            )
