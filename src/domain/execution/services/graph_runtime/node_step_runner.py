from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field

from adapters.observability.logging import get_logger
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.execution_plan import CompiledEdge, ExecutionPlan
from domain.execution.services.graph_runtime.fallback_reason_resolver import (
    resolve_fallback_reason,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import (
    FALLBACK_REASON_METADATA_KEY,
    FALLBACK_SOURCE_NODE_METADATA_KEY,
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.execution.services.observability.hooks import ExecutionEventHook
from domain.execution.services.state_machine import AgentRunStatus, NodeRunStatus
from domain.flows.schemas.graph import EdgeKind
from domain.flows.services.flow_graph_validator import TERMINAL_NODE_TYPES
from domain.prompts.schemas.prompt import NodeType
from exceptions.service_exceptions import DomainValidationException


logger = get_logger(__name__)


class NodeStepStatus(StrEnum):
    ADVANCE = "ADVANCE"
    TERMINAL = "TERMINAL"
    NEEDS_INPUT = "NEEDS_INPUT"
    FAILED = "FAILED"


class NodeStepOutcome(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    status: NodeStepStatus
    node_type: str | None = None
    node_run_id: UUID | None = None
    node_data: Dict[str, Any] = Field(default_factory=dict)
    context: ExecutionContext | None = None
    next_node_id: str | None = None
    resume_to_node_id: str | None = None
    loop_edge_keys: List[str] = Field(default_factory=list)
    failure_reason: FlowFailureReason | None = None
    failure_exception: BaseException | None = None


class NodeStepRunner:
    """Executes a single graph node and decides the next node.

    Shared by the in-process RuntimeExecutor loop and the Temporal execute_node
    activity. Performs the per-node writes (node run, events, graph state
    checkpoint) but never the flow-level terminal writes, which belong to the
    caller that owns the traversal.
    """

    def __init__(
        self,
        repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
        registry: NodeRegistry,
        hook: ExecutionEventHook | None = None,
    ) -> None:
        self.repository = repository
        self.tracer = tracer
        self.registry = registry
        self.hook = hook

    async def run_step(
        self,
        *,
        context: ExecutionContext,
        plan: ExecutionPlan,
        iteration_counters: Dict[str, int],
        loop_limit: int,
    ) -> NodeStepOutcome:
        node_specs = plan.nodes
        edges = plan.adjacency_map.get(context.current_node_id, [])

        spec = node_specs.get(context.current_node_id)
        if spec is None:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                context=context,
                failure_reason=FlowFailureReason.NODE_NOT_FOUND,
            )

        node_type = spec.get("type")
        node_cls = self.registry.resolve(node_type)
        if node_cls is None:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                node_type=node_type,
                context=context,
                failure_reason=FlowFailureReason.UNKNOWN_NODE_TYPE,
            )

        context_metadata = dict(context.metadata or {})
        context_metadata["current_node_type"] = node_type
        context = context.model_copy(update={"metadata": context_metadata})

        try:
            node: NodeExecutor = node_cls()
        except Exception as exc:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                node_type=node_type,
                context=context,
                failure_reason=FlowFailureReason.STRUCTURAL_ERROR,
                failure_exception=exc,
            )

        node_run_id = await self.repository.create_node_run(
            flow_run_id=context.flow_run_id,
            node_id=UUID(context.current_node_id),
            correlation_id=context.correlation_id,
            input_payload={
                "input_payload": context.input_payload,
                "state": context.state,
                "memory": context.memory,
                "metadata": context.metadata,
            },
            output_payload={},
            status=NodeRunStatus.RUNNING,
            canonical_status=NodeRunStatus.RUNNING,
        )

        context = context.model_copy(update={"current_node_run_id": node_run_id})

        await self._emit_node_started(context)

        config = spec.get("config") or {}
        with self.tracer.observe(
            as_type="span",
            name=f"domain.execution.graph_runtime.executor.node.{node_type}",
            input=context.snapshot(),
            metadata={"node_type": node_type},
        ) as node_handle:
            try:
                node_result: NodeResult = await node.execute(context, config)
            except Exception as exc:
                logger.exception(
                    "graph_node_execution_failed",
                    flow_run_id=str(context.flow_run_id),
                    node_run_id=str(node_run_id),
                    node_id=context.current_node_id,
                    node_type=str(node_type),
                    error_type=type(exc).__name__,
                )
                if node_handle:
                    node_handle.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"status": "failed"},
                    )
                return NodeStepOutcome(
                    status=NodeStepStatus.FAILED,
                    node_type=node_type,
                    node_run_id=node_run_id,
                    context=context,
                    failure_reason=FlowFailureReason.STRUCTURAL_ERROR,
                    failure_exception=exc,
                )
            if node_handle and node_result is not None:
                node_handle.success(output=node_result.model_dump(mode="json"))
        context.node_output = node_result.data

        status = self._map_status(node_result.status)
        await self.repository.update_node_run_result(
            node_run_id=node_run_id,
            output_payload=node_result.model_dump(mode="json"),
            status=status,
            canonical_status=status,
        )

        await self._record_usage(context=context, node_run_id=node_run_id, node_result=node_result)

        new_state = dict(node_result.next_state or context.state)
        snap = dict(new_state.get(NODE_OUTPUTS_BY_NODE_ID_KEY) or {})
        if context.current_node_id:
            out_data = node_result.data if isinstance(node_result.data, dict) else {}
            snap[str(context.current_node_id)] = out_data
        new_state[NODE_OUTPUTS_BY_NODE_ID_KEY] = snap
        if node_result.memory is not None:
            new_memory = list(node_result.memory)
        else:
            new_memory = list(context.memory)
        resume_to_node_id = None
        if node_result.status == NodeExecutionStatus.NEEDS_INPUT:
            resume_to_node_id = config.get("resume_to_node_id") or context.current_node_id

        await self._emit_node_completed(context, node_result)

        await self.repository.upsert_graph_state(
            flow_run_id=context.flow_run_id,
            state={
                "current_node_id": context.current_node_id,
                "state": new_state,
                "memory": new_memory,
                "resume_to_node_id": resume_to_node_id,
                "metadata": context.metadata,
            },
            last_node_run_id=node_run_id,
        )

        if node_result.status == NodeExecutionStatus.NEEDS_INPUT:
            return NodeStepOutcome(
                status=NodeStepStatus.NEEDS_INPUT,
                node_type=node_type,
                node_run_id=node_run_id,
                node_data=node_result.data or {},
                context=context,
                resume_to_node_id=resume_to_node_id,
            )

        if node_type in TERMINAL_NODE_TYPES:
            return NodeStepOutcome(
                status=NodeStepStatus.TERMINAL,
                node_type=node_type,
                node_run_id=node_run_id,
                node_data=node_result.data or {},
                context=context,
            )

        loop_edge_keys: List[str] = []
        try:
            matching = await self._evaluate_edges(
                edges,
                context,
                node_result.data,
                iteration_counters=iteration_counters,
                loop_limit=loop_limit,
                loop_edge_keys=loop_edge_keys,
            )
        except DomainValidationException as exc:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                node_type=node_type,
                node_run_id=node_run_id,
                node_data=node_result.data or {},
                context=context,
                loop_edge_keys=loop_edge_keys,
                failure_reason=FlowFailureReason.EDGE_EVALUATION_ERROR,
                failure_exception=exc,
            )

        if not matching:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                node_type=node_type,
                node_run_id=node_run_id,
                node_data=node_result.data or {},
                context=context,
                loop_edge_keys=loop_edge_keys,
                failure_reason=FlowFailureReason.NO_MATCHING_EDGE,
            )
        if len(matching) > 1:
            return NodeStepOutcome(
                status=NodeStepStatus.FAILED,
                node_type=node_type,
                node_run_id=node_run_id,
                node_data=node_result.data or {},
                context=context,
                loop_edge_keys=loop_edge_keys,
                failure_reason=FlowFailureReason.MULTIPLE_MATCHING_EDGES,
            )

        next_node_id = matching[0]
        update_payload: Dict[str, Any] = {
            "current_node_id": next_node_id,
            "state": new_state,
            "memory": new_memory,
            "node_output": node_result.data,
        }
        next_spec = node_specs.get(next_node_id)
        if next_spec is not None and next_spec.get("type") == NodeType.HumanFallback.value:
            new_metadata = dict(context.metadata or {})
            new_metadata[FALLBACK_SOURCE_NODE_METADATA_KEY] = context.current_node_id
            new_metadata[FALLBACK_REASON_METADATA_KEY] = resolve_fallback_reason(
                source_node_type=node_type,
                node_output=node_result.data,
            ).value
            update_payload["metadata"] = new_metadata

        return NodeStepOutcome(
            status=NodeStepStatus.ADVANCE,
            node_type=node_type,
            node_run_id=node_run_id,
            node_data=node_result.data or {},
            context=context.model_copy(update=update_payload),
            next_node_id=next_node_id,
            loop_edge_keys=loop_edge_keys,
        )

    async def _record_usage(
        self,
        *,
        context: ExecutionContext,
        node_run_id: UUID,
        node_result: NodeResult,
    ) -> None:
        """Persist what the node spent: an AgentRun when an agent governed it, always a ledger row.

        Failures here are logged and swallowed — accounting must never fail a node that already
        produced its result, and the ledger is reconcilable from execution events.
        """

        usage = node_result.usage
        if usage is None:
            return

        agent_run_id: UUID | None = None
        try:
            if usage.agent_version_id is not None:
                agent_run_id = await self.repository.create_agent_run(
                    tenant_id=context.tenant_id,
                    node_run_id=node_run_id,
                    agent_version_id=usage.agent_version_id,
                    correlation_id=context.correlation_id,
                    input_payload={"task_type": usage.task_type},
                    model=usage.provider_model,
                    ai_execution_policy_version_id=usage.ai_execution_policy_version_id,
                    status=AgentRunStatus.COMPLETED,
                    canonical_status=AgentRunStatus.COMPLETED,
                )
                await self.repository.update_agent_run_result(
                    agent_run_id=agent_run_id,
                    status=AgentRunStatus.COMPLETED,
                    canonical_status=AgentRunStatus.COMPLETED,
                    output=node_result.data if isinstance(node_result.data, dict) else {},
                    error=None,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    estimated_cost=float(usage.cost_usd) if usage.cost_usd is not None else None,
                )

            await self.repository.record_llm_usage(
                tenant_id=context.tenant_id,
                flow_run_id=context.flow_run_id,
                node_run_id=node_run_id,
                agent_run_id=agent_run_id,
                session_id=context.session_id,
                provider=usage.provider,
                provider_model=usage.provider_model,
                task_type=usage.task_type,
                inference_layer=usage.inference_layer,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
                latency_ms=usage.latency_ms,
            )
        except Exception:
            logger.exception(
                "llm_usage_not_recorded",
                flow_run_id=str(context.flow_run_id),
                node_run_id=str(node_run_id),
            )

    async def _emit_node_started(self, context: ExecutionContext) -> None:
        node_id = UUID(context.current_node_id) if context.current_node_id else None
        if self.hook:
            await self.hook.on_node_start(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=node_id,
                payload={"node_id": context.current_node_id},
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                event_type=ExecutionEventType.NodeStarted,
                payload={"node_id": context.current_node_id},
                correlation_id=context.correlation_id,
                causation_id=None,
                schema_version=1,
            )

    async def _emit_node_completed(
        self, context: ExecutionContext, node_result: NodeResult
    ) -> None:
        payload = {
            "node_id": context.current_node_id,
            "status": node_result.status,
            "payload": node_result.data,
            "error": node_result.error,
            "metrics": node_result.metrics,
        }
        if self.hook:
            await self.hook.on_node_complete(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=UUID(context.current_node_id) if context.current_node_id else None,
                payload=payload,
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                event_type=ExecutionEventType.NodeCompleted,
                payload=payload,
                correlation_id=context.correlation_id,
                causation_id=None,
                schema_version=1,
            )

    async def _evaluate_edges(
        self,
        edges: List[CompiledEdge],
        context: ExecutionContext,
        node_output: Dict[str, object],
        *,
        iteration_counters: Dict[str, int],
        loop_limit: int,
        loop_edge_keys: List[str],
    ) -> List[str]:
        current_node_id = context.current_node_id
        candidates: List[str] = []
        for edge in edges:
            if edge.from_node != current_node_id:
                continue
            if edge.edge_kind == EdgeKind.LOOP:
                key = f"{edge.from_node}->{edge.to_node}"
                loop_edge_keys.append(key)
                iteration_counters[key] = iteration_counters.get(key, 0) + 1
                if iteration_counters[key] > loop_limit:
                    raise DomainValidationException(message="loop_iteration_limit_exceeded")
            result = EdgeEvaluator.is_true(
                "",
                node_output,
                compiled_condition=edge.compiled_condition,
            )
            candidates.append(edge.to_node if result else None)
            await self._emit_edge_evaluated(
                context=context,
                to_node=edge.to_node,
                result=result,
            )
        candidates = [c for c in candidates if c is not None]
        return candidates

    async def _emit_edge_evaluated(
        self,
        *,
        context: ExecutionContext,
        to_node: str,
        result: bool,
    ) -> None:
        current_node_id = context.current_node_id
        payload = {
            "from_node": current_node_id,
            "to_node": to_node,
            "result": result,
        }
        if self.hook:
            await self.hook.on_edge_evaluated(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=UUID(current_node_id) if current_node_id else None,
                edge_id=f"{current_node_id}->{to_node}",
                payload=payload,
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                event_type=ExecutionEventType.EdgeEvaluated,
                payload=payload,
                correlation_id=context.correlation_id,
                causation_id=None,
                schema_version=1,
            )

    @staticmethod
    def _map_status(status: NodeExecutionStatus) -> NodeRunStatus:
        if status == NodeExecutionStatus.SUCCESS:
            return NodeRunStatus.COMPLETED
        if status == NodeExecutionStatus.ERROR:
            return NodeRunStatus.FAILED
        return NodeRunStatus.PENDING
