from __future__ import annotations

import contextlib
from typing import Dict, List
from uuid import UUID
from domain.execution.services.graph_runtime.types import NodeExecutor
from domain.execution.services.graph_runtime.types import NodeResult
from domain.execution.schemas.execution import FlowRunInput
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
)
from domain.execution.services.graph_runtime.execution_plan import (
    ExecutionPlan,
    CompiledEdge,
)
from domain.execution.services.observability.hooks import ExecutionEventHook
from domain.execution.services.state_machine import NodeRunStatus
from domain.flows.schemas.graph import EdgeKind
from domain.flows.services.flow_graph_validator import TERMINAL_NODE_TYPES
from exceptions.service_exceptions import DomainValidationException
from domain.governance.schemas.runtime_policy import ResolvedRuntimePolicy
from domain.execution.ports.runtime_tracer import RuntimeTracerPort


class RuntimeExecutor:
    def __init__(
        self,
        repository: ExecutionRepository,
        registry: NodeRegistry | None = None,
        tracer: RuntimeTracerPort | None = None,
        hook: ExecutionEventHook | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or NodeRegistry()
        self.tracer = tracer
        self.hook = hook
        self._default_loop_limit = 10

    async def run(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID,
        input_payload: FlowRunInput,
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
        loop_limit = (
            runtime_policy.definition.limits.get(
                "max_loop_iterations", self._default_loop_limit
            )
            if runtime_policy and runtime_policy.definition.limits
            else self._default_loop_limit
        )
        metadata = {}
        if runtime_policy:
            metadata["runtime_policy"] = runtime_policy.definition.model_dump(mode="json")

        context = ExecutionContext(
            tenant_id=tenant_id,
            session_id=session_id,
            input_payload=input_payload.model_dump(mode="json"),
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            available_tools=plan.available_tools,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            current_node_id=plan.start_node_id,
            metadata=metadata,
        )
        adjacency = plan.adjacency_map
        node_specs = plan.nodes

        edge_count = sum(len(v) for v in adjacency.values()) or 1
        max_steps = max(
            len(plan.ordered_nodes) + edge_count + 2,
            loop_limit * max(len(adjacency), 1) + 2,
        )
        for _ in range(max_steps):
            edges = adjacency.get(context.current_node_id, [])
            spec = node_specs.get(context.current_node_id)
            if spec is None:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.NODE_NOT_FOUND,
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
                    reason=FlowFailureReason.UNKNOWN_NODE_TYPE,
                )
                return

            node: NodeExecutor = node_cls()

            if self.hook:
                await self.hook.on_node_start(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=UUID(context.current_node_id)
                    if context.current_node_id
                    else None,
                    payload={"node_id": context.current_node_id},
                    causation_id=None,
                    schema_version=1,
                )
            else:
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
            node_result: NodeResult = await node.execute(context, config)
            context.node_output = node_result.payload

            node_run_id = await self.repository.create_node_run(
                flow_run_id=flow_run_id,
                node_id=UUID(context.current_node_id),
                correlation_id=correlation_id,
                input_payload={
                    "input_payload": input_payload.model_dump(mode='json'),
                    "state": context.state,
                    "memory": context.memory,
                    "metadata": context.metadata,
                },
                output_payload=node_result.model_dump(),
                status=self._map_status(node_result.status),
                canonical_status=self._map_status(node_result.status),
            )

            new_state = node_result.next_state or context.state
            new_memory = list(context.memory)
            if node_result.memory_append:
                new_memory.append(node_result.memory_append)

            if self.hook:
                await self.hook.on_node_complete(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=UUID(context.current_node_id)
                    if context.current_node_id
                    else None,
                    payload={
                        "node_id": context.current_node_id,
                        "status": node_result.status,
                        "payload": node_result.payload,
                        "error": node_result.error,
                        "metrics": node_result.metrics,
                    },
                    causation_id=None,
                    schema_version=1,
                )
            else:
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.NodeCompleted,
                    payload={
                        "node_id": context.current_node_id,
                        "status": node_result.status,
                        "payload": node_result.payload,
                        "error": node_result.error,
                        "metrics": node_result.metrics,
                    },
                    correlation_id=correlation_id,
                    causation_id=None,
                    schema_version=1,
                )
            await self.repository.upsert_graph_state(
                flow_run_id=flow_run_id,
                state={
                    "current_node_id": context.current_node_id,
                    "state": new_state,
                    "memory": new_memory,
                },
                last_node_run_id=node_run_id,
            )

            if node_type in TERMINAL_NODE_TYPES:
                if self.hook:
                    await self.hook.on_flow_complete(
                        tenant_id=tenant_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        payload={
                            "terminated_at": context.current_node_id,
                            "payload": node_result.payload,
                        },
                        causation_id=None,
                        schema_version=1,
                    )
                else:
                    await self.repository.append_execution_event(
                        tenant_id=tenant_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        event_type=ExecutionEventType.FlowCompleted,
                        payload={
                            "terminated_at": context.current_node_id,
                            "payload": node_result.payload,
                        },
                        correlation_id=correlation_id,
                        causation_id=None,
                        schema_version=1,
                    )
                return

            try:
                matching = await self._evaluate_edges(
                    edges,
                    context.current_node_id,
                    node_result.payload,
                    iteration_counters=context.iteration_counters,
                    loop_limit=loop_limit,
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
                    reason=FlowFailureReason.NO_MATCHING_EDGE,
                )
                return
            if len(matching) > 1:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.MULTIPLE_MATCHING_EDGES,
                )
                return

            context = ExecutionContext(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_id=flow_id,
                flow_version_id=flow_version_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
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
            reason=FlowFailureReason.MAX_STEPS_EXCEEDED,
        )

    async def _evaluate_edges(
        self,
        edges: List[CompiledEdge],
        current_node_id: str,
        node_output: Dict[str, object],
        iteration_counters: Dict[str, int],
        *,
        loop_limit: int,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
    ) -> List[str]:
        candidates: List[str] = []
        for edge in edges:
            if edge.from_node != current_node_id:
                continue
            if edge.edge_kind == EdgeKind.LOOP:
                key = f"{edge.from_node}->{edge.to_node}"
                iteration_counters[key] = iteration_counters.get(key, 0) + 1
                if iteration_counters[key] > loop_limit:
                    raise DomainValidationException(
                        message="loop_iteration_limit_exceeded"
                    )
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
        if self.tracer:
            self.tracer.create_event(
                event_type=ExecutionEventType.EdgeEvaluated,
                input={
                    "from_node": current_node_id,
                    "to_node": to_node,
                    "result": result,
                },
            )
        if self.hook:
            edge_id = f"{current_node_id}->{to_node}"
            await self.hook.on_edge_evaluated(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                node_id=UUID(current_node_id) if current_node_id else None,
                edge_id=edge_id,
                payload={
                    "from_node": current_node_id,
                    "to_node": to_node,
                    "result": result,
                },
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.EdgeEvaluated,
                payload={
                    "from_node": current_node_id,
                    "to_node": to_node,
                    "result": result,
                },
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
        reason: FlowFailureReason,
    ) -> None:
        if self.tracer:
            self.tracer.create_event(
                event_type=ExecutionEventType.FlowFailed,
                input={
                    "reason": reason.value if hasattr(reason, "value") else str(reason)
                },
            )
        if self.hook:
            await self.hook.on_flow_failed(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                payload={
                    "reason": reason.value if hasattr(reason, "value") else str(reason)
                },
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.FlowFailed,
                payload={
                    "reason": reason.value if hasattr(reason, "value") else str(reason)
                },
                correlation_id=correlation_id,
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


GraphExecutor = RuntimeExecutor
