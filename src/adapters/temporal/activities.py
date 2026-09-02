from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from adapters.temporal.dtos import (
    ExecuteNodeInput,
    ExecuteNodeOutput,
    FinalizeFlowRunInput,
    FlowRunPlanSummary,
    FlowRunWorkflowInput,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.schemas.graph_state import GraphStateSnapshot
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan
from domain.execution.services.graph_runtime.node_step_runner import NodeStepStatus
from domain.execution.services.graph_runtime.types import (
    USER_CONTEXT_READ_GATE_STATE_KEY,
    ExecutionContext,
    UserContextEnrichmentMode,
)
from domain.execution.services.state_machine import FlowRunStatus, RunStatus
from exceptions.service_exceptions import format_exception

DEFAULT_LOOP_LIMIT = 10
DEFAULT_MAX_NODE_DURATION_MS = 30_000
DEFAULT_MAX_TOTAL_DURATION_MS = 120_000
DEFAULT_MAX_RETRIES = 3


class FlowRunActivities:
    """Temporal activities backing FlowRunWorkflow.

    Every DB write and every node execution happens here. The workflow itself
    carries only identifiers and control flags, so node state, memory and tool
    catalogues never enter workflow history.
    """

    def __init__(
        self,
        execution_service: ExecutionService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.execution_service = execution_service
        self.tracer = tracer
        self.repository = execution_service.repository
        self.step_runner = execution_service.runtime.step_runner
        self.hook = execution_service.hook
        self.plan_compiler = execution_service.plan_compiler
        self.policy_resolver = execution_service.policy_resolver
        self.cache_adapter = execution_service.cache_adapter
        self.idempotency = execution_service.idempotency

    @activity.defn
    async def prepare_flow_run(self, payload: FlowRunWorkflowInput) -> FlowRunPlanSummary:
        flow_run_id = UUID(payload.flow_run_id)
        flow_run = await self.repository.get_flow_run(flow_run_id)
        if flow_run is None:
            raise ApplicationError(
                "flow_run_not_found",
                type="NotFoundServiceException",
                non_retryable=True,
            )

        plan = await self._resolve_plan(flow_run)
        runtime_policy = await self.policy_resolver.resolve(
            tenant_id=UUID(payload.tenant_id),
            flow_id=UUID(payload.flow_id),
        )
        definition = runtime_policy.definition.model_dump(mode="json")
        limits = definition.get("limits")
        if not isinstance(limits, dict):
            limits = {}

        loop_limit = _positive_int(limits.get("max_loop_iterations"), DEFAULT_LOOP_LIMIT)
        adjacency = plan.adjacency_map
        edge_count = sum(len(v) for v in adjacency.values()) or 1
        max_steps = max(
            len(plan.ordered_nodes) + edge_count + 2,
            loop_limit * max(len(adjacency), 1) + 2,
        )

        existing_state = await self.repository.get_graph_state(flow_run_id)
        if existing_state is None:
            context = self._build_initial_context(
                payload=payload,
                flow_run=flow_run,
                plan=plan,
                definition=definition,
            )
            await self.repository.upsert_graph_state(
                flow_run_id=flow_run_id,
                state={
                    "current_node_id": context.current_node_id,
                    "state": context.state,
                    "memory": context.memory,
                    "resume_to_node_id": None,
                    "metadata": context.metadata,
                },
                last_node_run_id=None,
            )

        await self.repository.set_flow_run_status(
            flow_run_id=flow_run_id,
            status=RunStatus.RUNNING,
            canonical_status=FlowRunStatus.RUNNING,
        )

        llm_policy = definition.get("llm")
        if not isinstance(llm_policy, dict):
            llm_policy = {}
        tools_policy = definition.get("tools")
        if not isinstance(tools_policy, dict):
            tools_policy = {}

        return FlowRunPlanSummary(
            start_node_id=payload.start_node_id or plan.start_node_id,
            max_steps=max_steps,
            loop_limit=loop_limit,
            node_count=len(plan.nodes),
            max_node_duration_ms=_positive_int(
                limits.get("max_node_duration_ms"), DEFAULT_MAX_NODE_DURATION_MS
            ),
            max_total_duration_ms=_positive_int(
                limits.get("max_total_duration_ms"), DEFAULT_MAX_TOTAL_DURATION_MS
            ),
            llm_max_retries=_positive_int(llm_policy.get("max_retries"), DEFAULT_MAX_RETRIES),
            tools_max_retries=_positive_int(tools_policy.get("max_retries"), DEFAULT_MAX_RETRIES),
        )

    @activity.defn
    async def execute_node(self, payload: ExecuteNodeInput) -> ExecuteNodeOutput:
        flow_run_id = UUID(payload.flow_run_id)
        flow_run = await self.repository.get_flow_run(flow_run_id)
        if flow_run is None:
            raise ApplicationError(
                "flow_run_not_found",
                type="NotFoundServiceException",
                non_retryable=True,
            )
        graph_state = await self.repository.get_graph_state(flow_run_id)
        if graph_state is None:
            raise ApplicationError(
                "graph_state_not_found",
                type="NotFoundServiceException",
                non_retryable=True,
            )

        if flow_run.interaction_id is None:
            raise ApplicationError(
                "flow_run_interaction_missing",
                type="DomainValidationException",
                non_retryable=True,
            )

        plan = await self._resolve_plan(flow_run)
        snapshot = GraphStateSnapshot.model_validate(graph_state.state or {})
        context = ExecutionContext(
            tenant_id=UUID(payload.tenant_id),
            interaction_id=flow_run.interaction_id,
            user_id=flow_run.user_id,
            session_id=flow_run.session_id,
            input_payload=flow_run.input or {},
            flow_id=UUID(payload.flow_id),
            flow_version_id=flow_run.flow_version_id,
            available_tools=plan.available_tools,
            flow_run_id=flow_run_id,
            correlation_id=flow_run.correlation_id,
            trace_id=flow_run.trace_id,
            current_node_id=payload.node_id,
            metadata=snapshot.metadata,
            state=snapshot.state,
            memory=snapshot.memory,
        )

        trace_context: Dict[str, str] = {}
        if payload.trace_id:
            trace_context["trace_id"] = payload.trace_id
        if payload.parent_observation_id:
            trace_context["parent_span_id"] = payload.parent_observation_id

        with self.tracer.observe(
            as_type="span",
            name=f"flow.node.{payload.step_index}",
            input={
                "flow_run_id": payload.flow_run_id,
                "node_id": payload.node_id,
                "step_index": payload.step_index,
            },
            metadata={"attempt": activity.info().attempt},
            trace_context=trace_context or None,
        ):
            outcome = await self.step_runner.run_step(
                context=context,
                plan=plan,
                iteration_counters={},
                loop_limit=payload.loop_limit,
            )

        node_type = outcome.node_type or ""
        node_run_id = str(outcome.node_run_id) if outcome.node_run_id else None

        if outcome.status == NodeStepStatus.FAILED:
            return ExecuteNodeOutput(
                node_type=node_type,
                node_run_id=node_run_id,
                status="ERROR",
                loop_edge_keys=outcome.loop_edge_keys,
                failure_reason=(
                    outcome.failure_reason.value
                    if outcome.failure_reason
                    else FlowFailureReason.STRUCTURAL_ERROR.value
                ),
            )

        if outcome.status == NodeStepStatus.NEEDS_INPUT:
            return ExecuteNodeOutput(
                node_type=node_type,
                node_run_id=node_run_id,
                status="NEEDS_INPUT",
                resume_to_node_id=outcome.resume_to_node_id,
            )

        if outcome.status == NodeStepStatus.TERMINAL:
            return ExecuteNodeOutput(
                node_type=node_type,
                node_run_id=node_run_id,
                status="SUCCESS",
                terminal=True,
            )

        return ExecuteNodeOutput(
            node_type=node_type,
            node_run_id=node_run_id,
            status="SUCCESS",
            next_node_id=outcome.next_node_id,
            loop_edge_keys=outcome.loop_edge_keys,
        )

    @activity.defn
    async def finalize_flow_run(self, payload: FinalizeFlowRunInput) -> None:
        flow_run_id = UUID(payload.flow_run_id)
        node_data = await self._last_node_output(payload.last_node_run_id)

        if payload.outcome == "COMPLETED":
            await self.repository.complete_flow_run(
                flow_run_id=flow_run_id,
                status=FlowRunStatus.COMPLETED,
                output=node_data,
            )
            await self.repository.set_current_interaction_result_for_flow_run(
                flow_run_id=flow_run_id,
                output=node_data,
                result_node_run_id=_optional_uuid(payload.last_node_run_id),
            )
            await self._emit_flow_completed(payload, node_data)
        elif payload.outcome == "WAITING":
            await self.repository.set_flow_run_output(
                flow_run_id=flow_run_id,
                output=node_data,
            )
            await self.repository.set_current_interaction_result_for_flow_run(
                flow_run_id=flow_run_id,
                output=node_data,
                result_node_run_id=_optional_uuid(payload.last_node_run_id),
            )
            await self.repository.set_flow_run_status(
                flow_run_id=flow_run_id,
                status=RunStatus.WAITING_INPUT,
                canonical_status=FlowRunStatus.WAITING,
            )
        elif payload.outcome == "CANCELLED":
            await self.repository.set_flow_run_status(
                flow_run_id=flow_run_id,
                status=RunStatus.CANCELLED,
                canonical_status=FlowRunStatus.FAILED,
            )
        else:
            await self._fail_flow(payload)

        await self._release_idempotency(payload)
        self.tracer.flush()

    async def _fail_flow(self, payload: FinalizeFlowRunInput) -> None:
        flow_run_id = UUID(payload.flow_run_id)
        reason = _failure_reason(payload.failure_reason)
        error_detail = await format_exception(
            reason,
            payload.correlation_id,
            ApplicationError(reason.value, type=reason.value),
        )
        await self.repository.fail_flow_run(
            flow_run_id=flow_run_id,
            failure_reason=reason,
            error=error_detail,
        )
        if self.hook:
            await self.hook.on_flow_failed(
                tenant_id=UUID(payload.tenant_id),
                user_id=payload.user_id,
                session_id=UUID(payload.session_id),
                flow_run_id=flow_run_id,
                correlation_id=UUID(payload.correlation_id),
                payload={"reason": reason},
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=UUID(payload.tenant_id),
                session_id=UUID(payload.session_id),
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.FlowFailed,
                payload={"reason": reason},
                correlation_id=UUID(payload.correlation_id),
                causation_id=None,
                schema_version=1,
            )

    async def _emit_flow_completed(
        self, payload: FinalizeFlowRunInput, node_data: Dict[str, Any]
    ) -> None:
        flow_run_id = UUID(payload.flow_run_id)
        graph_state = await self.repository.get_graph_state(flow_run_id)
        memory_extraction_config = None
        if graph_state is not None:
            snapshot = GraphStateSnapshot.model_validate(graph_state.state or {})
            runtime_policy = snapshot.metadata.get("runtime_policy")
            if isinstance(runtime_policy, dict):
                extracted_config = runtime_policy.get("memory_extraction")
                if isinstance(extracted_config, dict):
                    memory_extraction_config = extracted_config
        event_payload = {
            "terminated_at": payload.last_node_id,
            "payload": node_data,
            "memory_extraction_config": memory_extraction_config,
        }
        if self.hook:
            await self.hook.on_flow_complete(
                tenant_id=UUID(payload.tenant_id),
                user_id=payload.user_id,
                session_id=UUID(payload.session_id),
                flow_run_id=flow_run_id,
                correlation_id=UUID(payload.correlation_id),
                payload=event_payload,
                causation_id=None,
                schema_version=1,
            )
        else:
            await self.repository.append_execution_event(
                tenant_id=UUID(payload.tenant_id),
                session_id=UUID(payload.session_id),
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.FlowCompleted,
                payload=event_payload,
                correlation_id=UUID(payload.correlation_id),
                causation_id=None,
                schema_version=1,
            )

    async def _release_idempotency(self, payload: FinalizeFlowRunInput) -> None:
        if not payload.idempotency_key:
            return
        await self.idempotency.set_result(
            payload.idempotency_key,
            {
                "flow_run_id": payload.flow_run_id,
                "outcome": payload.outcome,
            },
        )

    async def _last_node_output(self, node_run_id: str | None) -> Dict[str, Any]:
        if not node_run_id:
            return {}
        node_run = await self.repository.get_node_run(UUID(node_run_id))
        if node_run is None:
            return {}
        output_payload = node_run.output or {}
        data = output_payload.get("data")
        return data if isinstance(data, dict) else {}

    def _build_initial_context(
        self,
        *,
        payload: FlowRunWorkflowInput,
        flow_run: Any,
        plan: ExecutionPlan,
        definition: Dict[str, Any],
    ) -> ExecutionContext:
        metadata: Dict[str, Any] = {}
        if definition:
            metadata["runtime_policy"] = definition

        context = ExecutionContext(
            tenant_id=UUID(payload.tenant_id),
            interaction_id=UUID(payload.interaction_id),
            user_id=payload.user_id,
            session_id=UUID(payload.session_id),
            input_payload=flow_run.input or {},
            flow_id=UUID(payload.flow_id),
            flow_version_id=UUID(payload.flow_version_id),
            available_tools=plan.available_tools,
            flow_run_id=UUID(payload.flow_run_id),
            correlation_id=UUID(payload.correlation_id),
            trace_id=UUID(payload.trace_id) if payload.trace_id else None,
            current_node_id=payload.start_node_id or plan.start_node_id,
            metadata=metadata,
            state={},
            memory=[],
        )

        user_context_policy = definition.get("user_context_enrichment", {})
        if isinstance(user_context_policy, dict) and bool(user_context_policy.get("enabled")):
            mode = (
                UserContextEnrichmentMode.GATED
                if bool(user_context_policy.get("gating"))
                else UserContextEnrichmentMode.LEGACY
            )
            context.state[USER_CONTEXT_READ_GATE_STATE_KEY] = {
                "enabled": True,
                "published": False,
                "published_by_node_id": None,
                "published_at": None,
                "layers": {},
                "mode": str(mode),
            }

        return context

    async def _resolve_plan(self, flow_run: Any) -> ExecutionPlan:
        graph_snapshot = None
        if flow_run.flow_graph_snapshot_id:
            graph_snapshot = await self.repository.get_flow_graph_snapshot(
                flow_run.flow_graph_snapshot_id
            )
        if graph_snapshot is None:
            graph_snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(
                flow_run.flow_version_id
            )
        if graph_snapshot is None:
            raise ApplicationError(
                "flow_graph_snapshot_not_found",
                type="NotFoundServiceException",
                non_retryable=True,
            )

        cached_plan = await self.cache_adapter.get(graph_snapshot.graph_hash)
        if cached_plan:
            return ExecutionPlan.model_validate(cached_plan)

        plan = self.plan_compiler.compile(
            graph_snapshot.snapshot,
            graph_snapshot.graph_hash,
            available_tools=[],
        )
        await self.cache_adapter.set(graph_snapshot.graph_hash, plan.model_dump(mode="json"))
        return plan


def _positive_int(raw: object, fallback: int) -> int:
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return value if value >= 1 else fallback


def _optional_uuid(raw: str | None) -> UUID | None:
    return UUID(raw) if raw else None


def _failure_reason(raw: str | None) -> FlowFailureReason:
    if raw is None:
        return FlowFailureReason.STRUCTURAL_ERROR
    try:
        return FlowFailureReason(raw)
    except ValueError:
        return FlowFailureReason.STRUCTURAL_ERROR
