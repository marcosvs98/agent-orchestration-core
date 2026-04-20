from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict, List
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
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    USER_CONTEXT_READ_GATE_STATE_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    UserContextEnrichmentMode,
)
from domain.execution.services.graph_runtime.execution_plan import (
    ExecutionPlan,
    CompiledEdge,
)
from domain.execution.services.observability.hooks import ExecutionEventHook
from domain.execution.services.state_machine import (
    FlowRunStatus,
    NodeRunStatus,
    RunStatus,
)
from domain.flows.schemas.graph import EdgeKind
from domain.flows.services.flow_graph_validator import TERMINAL_NODE_TYPES
from exceptions.service_exceptions import (
    format_exception,
    DomainValidationException,
)
from domain.governance.schemas.runtime_policy import ResolvedRuntimePolicy
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.prompts.schemas.prompt import NodeType


class RuntimeExecutor:
    def __init__(
        self,
        repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
        registry: NodeRegistry | None = None,
        hook: ExecutionEventHook | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or NodeRegistry(tracer=tracer)
        self.tracer = tracer
        self.hook = hook
        self._default_loop_limit = 10

    async def run(
        self,
        *,
        tenant_id: UUID,
        interaction_id: UUID,
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
        start_node_id: str | None = None,
        initial_state: dict[str, object] | None = None,
        initial_memory: list[dict[str, object]] | None = None,
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        definition_dump = (
            runtime_policy.definition.model_dump(mode="json") if runtime_policy else {}
        )
        if definition_dump:
            limits = definition_dump.get("limits")
            if not isinstance(limits, dict):
                limits = {}
            raw_loop = limits.get("max_loop_iterations")
            if raw_loop is None:
                loop_limit = self._default_loop_limit
            else:
                try:
                    loop_limit = int(raw_loop)
                except (TypeError, ValueError):
                    loop_limit = self._default_loop_limit
                if loop_limit < 1:
                    loop_limit = self._default_loop_limit
        else:
            loop_limit = self._default_loop_limit
        metadata = {}
        if definition_dump:
            metadata["runtime_policy"] = definition_dump
        trace_user_id = trace_context.user_id if trace_context is not None else None
        if trace_user_id is None:
            raise DomainValidationException(message="user_id_required")

        context = ExecutionContext(
            tenant_id=tenant_id,
            interaction_id=interaction_id,
            user_id=trace_user_id,
            session_id=session_id,
            input_payload=input_payload.model_dump(mode="json"),
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            available_tools=plan.available_tools,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            current_node_id=start_node_id or plan.start_node_id,
            metadata=metadata,
            state=initial_state or {},
            memory=initial_memory or [],
            on_content_delta=on_content_delta,
        )
        user_context_policy = definition_dump.get("user_context_enrichment", {})
        if isinstance(user_context_policy, dict) and bool(user_context_policy.get("enabled")):
            gate_key = USER_CONTEXT_READ_GATE_STATE_KEY
            handle = context.state.get(gate_key)
            if not isinstance(handle, dict):
                handle = {}
            mode = (
                UserContextEnrichmentMode.GATED
                if bool(user_context_policy.get("gating"))
                else UserContextEnrichmentMode.LEGACY
            )
            merged_handle = {
                "enabled": True,
                "published": bool(handle.get("published", False)),
                "published_by_node_id": handle.get("published_by_node_id"),
                "published_at": handle.get("published_at"),
                "layers": handle.get("layers") if isinstance(handle.get("layers"), dict) else {},
                "mode": str(handle.get("mode") or mode),
            }
            context.state[gate_key] = merged_handle

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
                    user_id=context.user_id,
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
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.UNKNOWN_NODE_TYPE,
                )
                return

            context_metadata = dict(context.metadata or {})
            context_metadata["current_node_type"] = node_type
            context = context.model_copy(update={"metadata": context_metadata})

            node: NodeExecutor = node_cls()

            node_run_id = await self.repository.create_node_run(
                flow_run_id=flow_run_id,
                node_id=UUID(context.current_node_id),
                correlation_id=correlation_id,
                input_payload={
                    "input_payload": input_payload.model_dump(mode="json"),
                    "state": context.state,
                    "memory": context.memory,
                    "metadata": context.metadata,
                },
                output_payload={},
                status=NodeRunStatus.RUNNING,
                canonical_status=NodeRunStatus.RUNNING,
            )

            context = context.model_copy(update={"current_node_run_id": node_run_id})

            if self.hook:
                await self.hook.on_node_start(
                    tenant_id=tenant_id,
                    user_id=trace_user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=UUID(context.current_node_id) if context.current_node_id else None,
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
                    if node_handle:
                        node_handle.error(
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            output={"status": "failed"},
                        )
                    await self._fail_flow(
                        tenant_id=tenant_id,
                        user_id=context.user_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        reason=FlowFailureReason.STRUCTURAL_ERROR,
                        exc=exc,
                    )
                    return
                if node_handle and node_result is not None:
                    node_handle.success(output=node_result.model_dump(mode="json"))
            context.node_output = node_result.data

            status = self._map_status(node_result.status)
            await self.repository.update_node_run_result(
                node_run_id=node_run_id,
                output_payload=node_result.model_dump(),
                status=status,
                canonical_status=status,
            )

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

            if self.hook:
                await self.hook.on_node_complete(
                    tenant_id=tenant_id,
                    user_id=trace_user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=UUID(context.current_node_id) if context.current_node_id else None,
                    payload={
                        "node_id": context.current_node_id,
                        "status": node_result.status,
                        "payload": node_result.data,
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
                        "payload": node_result.data,
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
                    "resume_to_node_id": resume_to_node_id,
                    "metadata": context.metadata,
                },
                last_node_run_id=node_run_id,
            )

            if node_result.status == NodeExecutionStatus.NEEDS_INPUT:
                await self.repository.set_flow_run_output(
                    flow_run_id=flow_run_id,
                    output=node_result.data or {},
                )
                await self.repository.set_current_interaction_result_for_flow_run(
                    flow_run_id=flow_run_id,
                    output=node_result.data or {},
                    result_node_run_id=node_run_id,
                )
                await self.repository.set_flow_run_status(
                    flow_run_id=flow_run_id,
                    status=RunStatus.WAITING_INPUT,
                    canonical_status=FlowRunStatus.WAITING,
                )
                return

            if node_type in TERMINAL_NODE_TYPES:
                await self.repository.complete_flow_run(
                    flow_run_id=flow_run_id,
                    status=FlowRunStatus.COMPLETED,
                    output=node_result.data,
                )
                await self.repository.set_current_interaction_result_for_flow_run(
                    flow_run_id=flow_run_id,
                    output=node_result.data or {},
                    result_node_run_id=node_run_id,
                )
                memory_extraction_config = None
                if isinstance(context.metadata, dict):
                    runtime_policy = context.metadata.get("runtime_policy")
                    if isinstance(runtime_policy, dict):
                        extracted_config = runtime_policy.get("memory_extraction")
                        if isinstance(extracted_config, dict):
                            memory_extraction_config = extracted_config
                if self.hook:
                    await self.hook.on_flow_complete(
                        tenant_id=tenant_id,
                        user_id=trace_user_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        payload={
                            "terminated_at": context.current_node_id,
                            "payload": node_result.data,
                            "memory_extraction_config": memory_extraction_config,
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
                            "payload": node_result.data,
                            "memory_extraction_config": memory_extraction_config,
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
                    node_result.data,
                    iteration_counters=context.iteration_counters,
                    loop_limit=loop_limit,
                    tenant_id=tenant_id,
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                )
            except DomainValidationException as exc:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.EDGE_EVALUATION_ERROR,
                    exc=exc,
                )
                return
            if not matching:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.NO_MATCHING_EDGE,
                )
                return
            if len(matching) > 1:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=FlowFailureReason.MULTIPLE_MATCHING_EDGES,
                )
                return

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
                new_metadata["fallback_source_node"] = context.current_node_id
                update_payload["metadata"] = new_metadata
            context = context.model_copy(update=update_payload)
        await self._fail_flow(
            tenant_id=tenant_id,
            user_id=context.user_id,
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
        user_id: str,
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
                    raise DomainValidationException(message="loop_iteration_limit_exceeded")
            result = EdgeEvaluator.is_true(
                "",
                node_output,
                compiled_condition=edge.compiled_condition,
            )
            candidates.append(edge.to_node if result else None)
            await self._emit_edge_evaluated(
                tenant_id=tenant_id,
                user_id=user_id,
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
        user_id: str,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        current_node_id: str,
        to_node: str,
        result: bool,
    ) -> None:
        if self.hook:
            edge_id = f"{current_node_id}->{to_node}"
            await self.hook.on_edge_evaluated(
                tenant_id=tenant_id,
                user_id=user_id,
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
        user_id: str,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        reason: FlowFailureReason,
        exc: BaseException | None = None,
    ) -> None:
        if exc is None:
            exc = DomainValidationException(message=reason.value)
        error_detail = await format_exception(reason, str(correlation_id), exc)

        await self.repository.fail_flow_run(
            flow_run_id=flow_run_id,
            failure_reason=reason,
            error=error_detail,
        )

        if self.hook:
            await self.hook.on_flow_failed(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                payload={"reason": reason},
                causation_id=None,
                schema_version=1,
            )
        else:
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
    def _map_status(status: NodeExecutionStatus) -> NodeRunStatus:
        if status == NodeExecutionStatus.SUCCESS:
            return NodeRunStatus.COMPLETED
        if status == NodeExecutionStatus.ERROR:
            return NodeRunStatus.FAILED
        return NodeRunStatus.PENDING


GraphExecutor = RuntimeExecutor
