from __future__ import annotations

import contextlib
from typing import Any, Dict, List
from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import ExecutionContext, NodeResult
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan, CompiledEdge
from domain.flows.services.flow_graph_validator import TERMINAL_NODE_TYPES
from exceptions.service_exceptions import DomainValidationException
from domain.governance.schemas.runtime_policy import ResolvedRuntimePolicy
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer


class RuntimeExecutor:
    def __init__(
        self,
        repository: ExecutionRepository,
        registry: NodeRegistry | None = None,
        tracer: LangfuseRuntimeTracer | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or NodeRegistry()
        self.tracer = tracer
        self.loop_limit = 10

    async def run(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        trace_id: UUID | None,
        plan: ExecutionPlan,
        runtime_policy: ResolvedRuntimePolicy | None = None,
        trace_context=None,
    ) -> None:
        """Execute a compiled execution plan deterministically, persisting node runs and events."""
        context = ExecutionContext(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            current_node_id=plan.start_node_id,
            metadata={"runtime_policy": runtime_policy.definition.model_dump()} if runtime_policy else {},
        )
        adjacency = plan.adjacency_map
        node_specs = plan.nodes

        edge_count = sum(len(v) for v in adjacency.values()) or 1
        max_steps = max(
            len(plan.ordered_nodes) + edge_count + 2,
            self.loop_limit * max(len(adjacency), 1) + 2,
        )
        span_cm = (
            self.tracer.start_flow_span(trace=trace_context)
            if self.tracer and trace_context is not None
            else contextlib.nullcontext()
        )
        with span_cm:
            for _ in range(max_steps):
            edges = adjacency.get(context.current_node_id, [])
            spec = node_specs.get(context.current_node_id)
            if spec is None:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason="node_not_found",
                )
                return

            node_type = spec.get("type")
            node_cls = self.registry.resolve(node_type)
            if node_cls is None:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason="unknown_node_type",
                )
                return
            node = node_cls()

            node_span = (
                self.tracer.start_node_span(
                    node_id=context.current_node_id,
                    node_type=node_type,
                    input={"state": context.state, "metadata": context.metadata},
                )
                if self.tracer
                else contextlib.nullcontext()
            )
            with node_span:
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.NodeStarted,
                    payload={"node_id": context.current_node_id},
                    correlation_id=correlation_id,
                    causation_id=None,
                    schema_version=1,
                )

                config = spec.get("config")
                result = await node.execute(context, config)
                context.node_output = result.payload

            node_run_id = await self.repository.create_node_run(
                flow_run_id=flow_run_id,
                node_id=UUID(context.current_node_id),
                correlation_id=correlation_id,
                input_payload={
                    "state": context.state,
                    "memory": context.memory,
                    "metadata": context.metadata,
                },
                output_payload=result.model_dump(),
                status=self._map_status(result.status),
                canonical_status=self._map_status(result.status),
            )

            new_state = result.next_state or context.state
            new_memory = list(context.memory)
            if result.memory_append:
                new_memory.append(result.memory_append)

            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.NodeCompleted,
                payload={
                    "node_id": context.current_node_id,
                    "status": result.status,
                    "payload": result.payload,
                    "error": result.error,
                    "metrics": result.metrics,
                },
                correlation_id=correlation_id,
                causation_id=None,
                schema_version=1,
            )
            await self.repository.upsert_graph_state(
                flow_run_id=flow_run_id,
                state={"current_node_id": context.current_node_id, "state": new_state, "memory": new_memory},
                last_node_run_id=node_run_id,
            )

            if node_type in TERMINAL_NODE_TYPES:
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.FlowCompleted,
                    payload={"terminated_at": context.current_node_id, "payload": result.payload},
                    correlation_id=correlation_id,
                    causation_id=None,
                    schema_version=1,
                )
                return

            try:
                matching = await self._evaluate_edges(
                    edges,
                    context.current_node_id,
                    result.payload,
                    iteration_counters=context.iteration_counters,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                )
            except DomainValidationException as exc:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=str(exc),
                )
                return
            if not matching:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason="no_matching_edge",
                )
                return
            if len(matching) > 1:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason="multiple_matching_edges",
                )
                return

            context = ExecutionContext(
                tenant_id=tenant_id,
                flow_id=flow_id,
                flow_version_id=flow_version_id,
                flow_run_id=flow_run_id,
                current_node_id=matching[0],
                state=new_state,
                memory=new_memory,
                metadata=context.metadata,
                node_output={},
                iteration_counters=context.iteration_counters,
            )

        await self._fail_flow(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            reason="max_steps_exceeded",
        )

    async def _evaluate_edges(
        self,
        edges: List[CompiledEdge],
        current_node_id: str,
        node_output: Dict[str, object],
        iteration_counters: Dict[str, int],
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
    ) -> List[str]:
        candidates: List[str] = []
        for edge in edges:
            if edge.from_node != current_node_id:
                continue
            if edge.edge_kind == "LOOP":
                key = f"{edge.from_node}->{edge.to_node}"
                iteration_counters[key] = iteration_counters.get(key, 0) + 1
                if iteration_counters[key] > self.loop_limit:
                    raise DomainValidationException(message="loop_iteration_limit_exceeded")
            result = EdgeEvaluator.is_true(
                "",
                node_output,
                compiled_condition=edge.compiled_condition,
            )
            candidates.append(edge.to_node if result else None)
            await self._emit_edge_evaluated(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                current_node_id=current_node_id,
                to_node=edge.to_node,
                result=result,
            )
        candidates = [c for c in candidates if c is not None]
        return candidates

    async def _emit_edge_evaluated(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        current_node_id: str,
        to_node: str,
        result: bool,
    ) -> None:
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.EdgeEvaluated,
            payload={"from_node": current_node_id, "to_node": to_node, "result": result},
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )

    async def _fail_flow(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        reason: str,
    ) -> None:
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.FlowFailed,
            payload={"reason": reason},
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )

    @staticmethod
    def _map_status(status: str) -> str:
        if status == "SUCCESS":
            return "COMPLETED"
        if status == "ERROR":
            return "FAILED"
        return "NEEDS_INPUT"


GraphExecutor = RuntimeExecutor
