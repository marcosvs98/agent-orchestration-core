from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict
from uuid import UUID
from domain.execution.schemas.execution import FlowRunInput
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.services.graph_runtime.node_step_runner import (
    NodeStepRunner,
    NodeStepStatus,
)
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import (
    USER_CONTEXT_READ_GATE_STATE_KEY,
    ExecutionContext,
    UserContextEnrichmentMode,
)
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan
from domain.execution.services.observability.hooks import ExecutionEventHook
from domain.execution.services.state_machine import (
    FlowRunStatus,
    RunStatus,
)
from exceptions.service_exceptions import (
    format_exception,
    DomainValidationException,
)
from domain.governance.schemas.runtime_policy import ResolvedRuntimePolicy
from domain.execution.ports.runtime_tracer import RuntimeTracerPort


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
        self.step_runner = NodeStepRunner(
            repository=repository,
            tracer=tracer,
            registry=self.registry,
            hook=hook,
        )

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

        edge_count = sum(len(v) for v in adjacency.values()) or 1
        max_steps = max(
            len(plan.ordered_nodes) + edge_count + 2,
            loop_limit * max(len(adjacency), 1) + 2,
        )
        for _ in range(max_steps):
            outcome = await self.step_runner.run_step(
                context=context,
                plan=plan,
                iteration_counters=context.iteration_counters,
                loop_limit=loop_limit,
            )
            context = outcome.context or context

            if outcome.status == NodeStepStatus.FAILED:
                await self._fail_flow(
                    tenant_id=tenant_id,
                    user_id=context.user_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    reason=outcome.failure_reason,
                    exc=outcome.failure_exception,
                )
                return

            if outcome.status == NodeStepStatus.NEEDS_INPUT:
                await self.repository.set_flow_run_output(
                    flow_run_id=flow_run_id,
                    output=outcome.node_data,
                )
                await self.repository.set_current_interaction_result_for_flow_run(
                    flow_run_id=flow_run_id,
                    output=outcome.node_data,
                    result_node_run_id=outcome.node_run_id,
                )
                await self.repository.set_flow_run_status(
                    flow_run_id=flow_run_id,
                    status=RunStatus.WAITING_INPUT,
                    canonical_status=FlowRunStatus.WAITING,
                )
                return

            if outcome.status == NodeStepStatus.TERMINAL:
                await self._complete_flow(
                    context=context,
                    node_run_id=outcome.node_run_id,
                    node_data=outcome.node_data,
                    trace_user_id=trace_user_id,
                )
                return

            context = context.model_copy(update={"current_node_id": outcome.next_node_id})
        await self._fail_flow(
            tenant_id=tenant_id,
            user_id=context.user_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            reason=FlowFailureReason.MAX_STEPS_EXCEEDED,
        )

    async def _complete_flow(
        self,
        *,
        context: ExecutionContext,
        node_run_id: UUID | None,
        node_data: Dict[str, Any],
        trace_user_id: str,
    ) -> None:
        flow_run_id = context.flow_run_id
        await self.repository.complete_flow_run(
            flow_run_id=flow_run_id,
            status=FlowRunStatus.COMPLETED,
            output=node_data,
        )
        await self.repository.set_current_interaction_result_for_flow_run(
            flow_run_id=flow_run_id,
            output=node_data,
            result_node_run_id=node_run_id,
        )
        memory_extraction_config = None
        if isinstance(context.metadata, dict):
            runtime_policy = context.metadata.get("runtime_policy")
            if isinstance(runtime_policy, dict):
                extracted_config = runtime_policy.get("memory_extraction")
                if isinstance(extracted_config, dict):
                    memory_extraction_config = extracted_config
        payload = {
            "terminated_at": context.current_node_id,
            "payload": node_data,
            "memory_extraction_config": memory_extraction_config,
        }
        if self.hook:
            await self.hook.on_flow_complete(
                tenant_id=context.tenant_id,
                user_id=trace_user_id,
                session_id=context.session_id,
                flow_run_id=flow_run_id,
                correlation_id=context.correlation_id,
                payload=payload,
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.FlowCompleted,
                payload=payload,
                correlation_id=context.correlation_id,
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


GraphExecutor = RuntimeExecutor
