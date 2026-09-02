from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from adapters.observability.logging import get_logger
from domain.agents.ports.agent_task_runner import AgentTaskRunnerPort
from domain.agents.repositories.agent_delegation_repository import AgentDelegationRepository
from domain.agents.schemas.a2a import (
    A2ATaskExecution,
    A2ATaskExecutionResult,
    A2ATaskState,
)
from domain.agents.services.a2a_translator import A2ATranslator
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.agent_run_repository import AgentRunRepository
from domain.execution.schemas.agent_run import (
    DEFAULT_MAX_ITERATIONS,
    AgentRunArtifact,
    AgentRunContextItem,
    AgentRunCreate,
    AgentRunDelegation,
    AgentRunDetail,
    AgentRunEvent,
    AgentRunFinishReason,
    AgentRunMessage,
    AgentRunOrigin,
    AgentRunSummary,
    AgentRunToolCall,
    AgentRunToolGrant,
)
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.agent_runtime.agent_loop import (
    AgentCognitiveLoop,
    AgentLoopResult,
)
from domain.execution.services.agent_runtime.context_builder import AgentRunContextBuilder
from domain.execution.services.agent_runtime.definition import (
    AgentDefinition,
    AgentDefinitionResolver,
)
from domain.execution.services.agent_runtime.tool_grant import (
    ResolvedToolGrant,
    ToolGrantResolver,
)
from domain.execution.services.agent_runtime.types import AgentRunScope
from domain.execution.services.state_machine import AgentRunStatus, RunStatus
from exceptions.service_exceptions import (
    IdempotencyInProgressException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)
from infra.database.models.execution.agent_run import AgentRun as AgentRunModel

logger = get_logger(__name__)

FINAL_OUTPUT_ARTIFACT_NAME = "final-output"


class AgentRunService(AgentTaskRunnerPort):
    """Lifecycle of an agent execution: create, run, observe, cancel.

    Also the in-process A2A transport: a delegated task becomes another agent run here, with its
    own identity, grant and transcript, linked to the caller through ``parent_agent_run_id`` and
    the shared ``root_agent_run_id``.
    """

    def __init__(
        self,
        repository: AgentRunRepository,
        delegation_repository: AgentDelegationRepository,
        definition_resolver: AgentDefinitionResolver,
        grant_resolver: ToolGrantResolver,
        context_builder: AgentRunContextBuilder,
        loop: AgentCognitiveLoop,
        translator: A2ATranslator,
        idempotency: IdempotencyService,
        tracer: RuntimeTracerPort,
        default_max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.repository = repository
        self.delegation_repository = delegation_repository
        self.definition_resolver = definition_resolver
        self.grant_resolver = grant_resolver
        self.context_builder = context_builder
        self.loop = loop
        self.translator = translator
        self.idempotency = idempotency
        self.tracer = tracer
        self.default_max_iterations = default_max_iterations
        self._in_flight: dict[UUID, asyncio.Task] = {}

    async def create_agent_run(
        self,
        *,
        tenant_id: UUID,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request: AgentRunCreate,
        wait: bool,
    ) -> AgentRunSummary:
        definition = await self.definition_resolver.resolve(
            tenant_id=tenant_id, agent_id=request.agent_id
        )
        grant = await self.grant_resolver.resolve(
            tenant_id=tenant_id, definition=definition, requested=request.tools
        )

        key = self.idempotency.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        acquired = await self.idempotency.try_acquire(key)
        if not acquired:
            existing = await self.idempotency.get(key)
            if existing and "response" in existing:
                return AgentRunSummary.model_validate(existing["response"])
            raise IdempotencyInProgressException()

        agent_run_id = await self._create_run_record(
            tenant_id=tenant_id,
            principal_id=principal_id,
            definition=definition,
            grant=grant,
            instruction=request.instruction,
            payload=request.payload,
            context_items=request.context,
            max_iterations=request.max_iterations,
            correlation_id=request.correlation_id or uuid4(),
            origin=AgentRunOrigin.DIRECT,
            metadata=request.metadata,
            idempotency_key=idempotency_key,
        )

        if wait:
            await self._execute(
                tenant_id=tenant_id, principal_id=principal_id, agent_run_id=agent_run_id
            )
        else:
            task = asyncio.create_task(
                self._execute_detached(
                    tenant_id=tenant_id, principal_id=principal_id, agent_run_id=agent_run_id
                ),
                name=f"agent_run:{agent_run_id}",
            )
            self._in_flight[agent_run_id] = task

        summary = await self._load_summary(tenant_id=tenant_id, agent_run_id=agent_run_id)
        await self.idempotency.set_result(key, {"response": summary.model_dump(mode="json")})
        return summary

    async def get_agent_run(self, *, tenant_id: UUID, agent_run_id: UUID) -> AgentRunDetail:
        model = await self.repository.get_agent_run(tenant_id=tenant_id, agent_run_id=agent_run_id)
        if model is None:
            raise NotFoundServiceException(message="agent_run_not_found")
        messages = await self.repository.list_messages(agent_run_id=agent_run_id)
        events = await self.repository.list_events(agent_run_id=agent_run_id)
        artifacts = await self.repository.list_artifacts(agent_run_id=agent_run_id)
        tool_runs = await self.repository.list_tool_runs(agent_run_id=agent_run_id)
        delegations = await self.delegation_repository.list_delegations_for_agent_run(
            parent_agent_run_id=agent_run_id
        )
        tool_names_by_call_id = {
            message.tool_call_id: message.tool_name
            for message in messages
            if message.tool_call_id and message.tool_name
        }
        return AgentRunDetail(
            **self._summary_fields(model),
            input=model.input or {},
            context_snapshot=model.context_snapshot or {},
            tool_grant=model.tool_grant or {},
            messages=[
                AgentRunMessage(
                    sequence=message.message_sequence,
                    role=message.role,
                    content=message.content,
                    tool_call_id=message.tool_call_id,
                    tool_name=message.tool_name,
                    trust_level=message.trust_level,
                    source=message.source,
                )
                for message in messages
            ],
            tool_calls=[
                AgentRunToolCall(
                    tool_run_id=tool_run.tool_run_id,
                    tool_call_id=tool_run.tool_call_id or "",
                    tool_name=str(tool_names_by_call_id.get(tool_run.tool_call_id) or ""),
                    tool_config_id=tool_run.tool_config_id,
                    status=tool_run.canonical_status,
                    input=tool_run.input or {},
                    output=tool_run.output or {},
                    error=tool_run.error or {},
                )
                for tool_run in tool_runs
            ],
            events=[
                AgentRunEvent(
                    sequence=int(event.event_sequence),
                    type=event.type,
                    occurred_at=event.occurred_at.isoformat(),
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    payload=event.payload or {},
                )
                for event in events
            ],
            artifacts=[
                AgentRunArtifact(
                    artifact_id=f"{artifact.name}-{artifact.artifact_index}",
                    index=artifact.artifact_index,
                    name=artifact.name,
                    description=artifact.description,
                    parts=list(artifact.parts or []),
                )
                for artifact in artifacts
            ],
            delegations=[
                AgentRunDelegation(
                    agent_delegation_id=delegation.agent_delegation_id,
                    a2a_task_id=delegation.a2a_task_id,
                    a2a_context_id=delegation.a2a_context_id,
                    a2a_task_state=delegation.a2a_task_state,
                    transport=delegation.transport,
                    target_agent_id=delegation.target_agent_id,
                    child_agent_run_id=delegation.child_agent_run_id,
                )
                for delegation in delegations
            ],
        )

    async def list_agent_runs(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        flow_run_id: UUID | None = None,
        root_agent_run_id: UUID | None = None,
        parent_agent_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRunSummary]:
        models = await self.repository.list_agent_runs(
            tenant_id=tenant_id,
            agent_id=agent_id,
            flow_run_id=flow_run_id,
            root_agent_run_id=root_agent_run_id,
            parent_agent_run_id=parent_agent_run_id,
            limit=limit,
        )
        return [AgentRunSummary(**self._summary_fields(model)) for model in models]

    async def cancel_agent_run(self, *, tenant_id: UUID, agent_run_id: UUID) -> AgentRunSummary:
        """Stop a run that has not reached a terminal state.

        The in-flight task is only reachable from the process that accepted the run, so a run
        started elsewhere is marked cancelled and its worker observes that on its next write
        rather than being interrupted mid-turn.
        """

        model = await self.repository.get_agent_run(tenant_id=tenant_id, agent_run_id=agent_run_id)
        if model is None:
            raise NotFoundServiceException(message="agent_run_not_found")
        if model.canonical_status in {
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELLED.value,
        }:
            raise ResourceBlockedServiceException(message="agent_run_not_cancellable")

        task = self._in_flight.pop(agent_run_id, None)
        if task is not None and not task.done():
            task.cancel()
        await self.repository.finish_agent_run(
            agent_run_id=agent_run_id,
            status=RunStatus.CANCELLED.value,
            canonical_status=AgentRunStatus.CANCELLED.value,
            output={},
            error={"error": "cancelled"},
            finish_reason=AgentRunFinishReason.CANCELLED.value,
            iterations_used=int(model.iterations_used or 0),
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
            estimated_cost=float(model.estimated_cost) if model.estimated_cost else None,
        )
        await self.repository.append_event(
            agent_run_id=agent_run_id,
            tenant_id=tenant_id,
            event_type=ExecutionEventType.AgentRunAborted,
            payload={"reason": AgentRunFinishReason.CANCELLED.value},
            correlation_id=model.correlation_id,
        )
        return await self._load_summary(tenant_id=tenant_id, agent_run_id=agent_run_id)

    async def run_a2a_task(self, *, execution: A2ATaskExecution) -> A2ATaskExecutionResult:
        instruction = execution.message.text()
        payload = execution.message.data()
        try:
            definition = await self.definition_resolver.resolve(
                tenant_id=execution.tenant_id, agent_id=execution.target_agent_id
            )
            grant = await self.grant_resolver.resolve(
                tenant_id=execution.tenant_id,
                definition=definition,
                requested=AgentRunToolGrant(allowed_tool_names=execution.allowed_tool_names),
            )
            agent_run_id = await self._create_run_record(
                tenant_id=execution.tenant_id,
                principal_id=execution.principal_id,
                definition=definition,
                grant=grant,
                instruction=instruction,
                payload=payload,
                context_items=[],
                max_iterations=execution.max_iterations,
                correlation_id=execution.correlation_id,
                origin=AgentRunOrigin.A2A_DELEGATION,
                metadata={
                    "a2a_task_id": execution.task_id,
                    "a2a_context_id": execution.context_id,
                },
                idempotency_key=None,
                parent_agent_run_id=execution.parent_agent_run_id,
                root_agent_run_id=execution.root_agent_run_id,
                delegation_depth=execution.delegation_depth,
            )
        except Exception as exc:
            return A2ATaskExecutionResult(
                state=A2ATaskState.REJECTED,
                error={"error": type(exc).__name__, "detail": str(exc)},
            )

        result = await self._execute(
            tenant_id=execution.tenant_id,
            principal_id=execution.principal_id,
            agent_run_id=agent_run_id,
        )
        artifacts = [
            self.translator.build_output_artifact(
                index=artifact.artifact_index,
                name=str(artifact.name or FINAL_OUTPUT_ARTIFACT_NAME),
                description=artifact.description,
                text="\n".join(
                    str(part.get("text", ""))
                    for part in (artifact.parts or [])
                    if isinstance(part, dict) and part.get("kind") == "text"
                ),
            )
            for artifact in await self.repository.list_artifacts(agent_run_id=agent_run_id)
        ]
        return A2ATaskExecutionResult(
            state=A2ATaskState.COMPLETED
            if result.finish_reason == AgentRunFinishReason.FINAL_OUTPUT
            else A2ATaskState.FAILED,
            child_agent_run_id=agent_run_id,
            output_text=result.output_text,
            artifacts=artifacts,
            error=dict(result.error),
        )

    async def _create_run_record(
        self,
        *,
        tenant_id: UUID,
        principal_id: str,
        definition: AgentDefinition,
        grant: ResolvedToolGrant,
        instruction: str,
        payload: dict,
        context_items: list[AgentRunContextItem],
        max_iterations: int | None,
        correlation_id: UUID,
        origin: AgentRunOrigin,
        metadata: dict[str, str],
        idempotency_key: str | None,
        parent_agent_run_id: UUID | None = None,
        root_agent_run_id: UUID | None = None,
        delegation_depth: int = 0,
    ) -> UUID:
        agent_run_id = await self.repository.create_agent_run(
            tenant_id=tenant_id,
            agent_id=definition.agent_id,
            agent_version_id=definition.agent_version_id,
            correlation_id=correlation_id,
            origin=origin,
            input_payload={
                "instruction": instruction,
                "payload": payload,
                "metadata": metadata,
                "principal_id": principal_id,
            },
            context_snapshot={"items": [item.model_dump(mode="json") for item in context_items]},
            tool_grant=grant.snapshot(),
            max_iterations=max_iterations or self.default_max_iterations,
            model=definition.model_name,
            billing_policy_version_id=definition.billing_policy_version_id,
            ai_execution_policy_version_id=definition.ai_execution_policy_version_id,
            system_prompt_hash=definition.system_prompt_hash(),
            runtime_snapshot=definition.runtime_snapshot(),
            runtime_snapshot_hash=None,
            parent_agent_run_id=parent_agent_run_id,
            root_agent_run_id=root_agent_run_id,
            delegation_depth=delegation_depth,
            idempotency_key=idempotency_key,
        )
        await self.repository.append_event(
            agent_run_id=agent_run_id,
            tenant_id=tenant_id,
            event_type=ExecutionEventType.AgentRunStarted,
            payload={
                "agent_id": str(definition.agent_id),
                "agent_version_id": str(definition.agent_version_id),
                "origin": origin.value,
                "model": definition.model_name,
                "granted_tools": [tool.function_name for tool in grant.tools],
                "allow_agent_delegation": grant.allow_agent_delegation,
                "delegation_depth": delegation_depth,
                "parent_agent_run_id": str(parent_agent_run_id)
                if parent_agent_run_id is not None
                else None,
            },
            correlation_id=correlation_id,
        )
        return agent_run_id

    async def _execute_detached(
        self, *, tenant_id: UUID, principal_id: str, agent_run_id: UUID
    ) -> None:
        try:
            await self._execute(
                tenant_id=tenant_id, principal_id=principal_id, agent_run_id=agent_run_id
            )
        except asyncio.CancelledError:
            logger.info("agent_run_cancelled", agent_run_id=str(agent_run_id))
            raise
        finally:
            self._in_flight.pop(agent_run_id, None)

    async def _execute(
        self, *, tenant_id: UUID, principal_id: str, agent_run_id: UUID
    ) -> AgentLoopResult:
        model = await self.repository.get_agent_run(tenant_id=tenant_id, agent_run_id=agent_run_id)
        if model is None:
            raise NotFoundServiceException(message="agent_run_not_found")

        definition = await self.definition_resolver.resolve(
            tenant_id=tenant_id, agent_id=model.agent_id
        )
        grant = await self.grant_resolver.resolve(
            tenant_id=tenant_id,
            definition=definition,
            requested=self._grant_request_from_snapshot(model),
        )
        run_input = model.input or {}
        context_items = [
            AgentRunContextItem.model_validate(item)
            for item in (model.context_snapshot or {}).get("items", [])
        ]
        prompt_parts = self.context_builder.build(
            definition=definition,
            grant=grant,
            context_items=context_items,
            instruction=str(run_input.get("instruction") or ""),
            payload=run_input.get("payload") or {},
        )
        scope = AgentRunScope(
            tenant_id=tenant_id,
            principal_id=principal_id,
            agent_run_id=agent_run_id,
            agent_id=model.agent_id,
            correlation_id=model.correlation_id,
            root_agent_run_id=model.root_agent_run_id or agent_run_id,
            delegation_depth=int(model.delegation_depth or 0),
            interaction_metadata={
                str(key): str(value) for key, value in (run_input.get("metadata") or {}).items()
            },
        )

        await self.repository.mark_running(agent_run_id=agent_run_id)
        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.agent_runtime.run",
            metadata={
                "tenant_id": str(scope.tenant_id),
                "agent_run_id": str(agent_run_id),
                "agent_id": str(model.agent_id),
            },
            input={
                "agent_run_id": str(agent_run_id),
                "agent_id": str(model.agent_id),
                "origin": model.origin,
                "max_iterations": int(model.max_iterations or self.default_max_iterations),
            },
        ) as run_span:
            try:
                result = await self.loop.run(
                    scope=scope,
                    definition=definition,
                    grant=grant,
                    prompt_parts=prompt_parts,
                    max_iterations=int(model.max_iterations or self.default_max_iterations),
                    runner=self,
                )
            except Exception as exc:
                if run_span:
                    run_span.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"status": "error"},
                    )
                await self._finalize_failure(scope=scope, exc=exc)
                raise
            if run_span:
                run_span.success(
                    output={
                        "finish_reason": result.finish_reason.value,
                        "iterations_used": result.iterations_used,
                        "tool_call_count": result.tool_call_count,
                    }
                )

        await self._finalize(scope=scope, result=result)
        return result

    async def _finalize(self, *, scope: AgentRunScope, result: AgentLoopResult) -> None:
        succeeded = result.finish_reason == AgentRunFinishReason.FINAL_OUTPUT
        if succeeded and result.output_text:
            artifact = self.translator.build_output_artifact(
                index=1,
                name=FINAL_OUTPUT_ARTIFACT_NAME,
                description="Final answer produced by the agent run.",
                text=result.output_text,
            )
            await self.repository.append_artifact(
                agent_run_id=scope.agent_run_id,
                name=FINAL_OUTPUT_ARTIFACT_NAME,
                description=artifact.description,
                parts=[part.model_dump(mode="json") for part in artifact.parts],
                payload={"text": result.output_text},
            )
        await self.repository.finish_agent_run(
            agent_run_id=scope.agent_run_id,
            status=RunStatus.COMPLETED.value if succeeded else RunStatus.FAILED.value,
            canonical_status=AgentRunStatus.COMPLETED.value
            if succeeded
            else AgentRunStatus.FAILED.value,
            output={"text": result.output_text},
            error=dict(result.error),
            finish_reason=result.finish_reason.value,
            iterations_used=result.iterations_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=result.estimated_cost,
        )
        await self.repository.append_event(
            agent_run_id=scope.agent_run_id,
            tenant_id=scope.tenant_id,
            event_type=ExecutionEventType.AgentRunCompleted
            if succeeded
            else ExecutionEventType.AgentRunFailed,
            payload={
                "finish_reason": result.finish_reason.value,
                "iterations_used": result.iterations_used,
                "tool_call_count": result.tool_call_count,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            correlation_id=scope.correlation_id,
        )

    async def _finalize_failure(self, *, scope: AgentRunScope, exc: Exception) -> None:
        await self.repository.finish_agent_run(
            agent_run_id=scope.agent_run_id,
            status=RunStatus.FAILED.value,
            canonical_status=AgentRunStatus.FAILED.value,
            output={},
            error={"error": type(exc).__name__, "detail": str(exc)},
            finish_reason=AgentRunFinishReason.LLM_ERROR.value,
            iterations_used=0,
            input_tokens=None,
            output_tokens=None,
            estimated_cost=None,
        )
        await self.repository.append_event(
            agent_run_id=scope.agent_run_id,
            tenant_id=scope.tenant_id,
            event_type=ExecutionEventType.AgentRunFailed,
            payload={"error": type(exc).__name__},
            correlation_id=scope.correlation_id,
        )

    @staticmethod
    def _grant_request_from_snapshot(model: AgentRunModel) -> AgentRunToolGrant:
        """Rebuild the authorization from what was frozen when the run was created.

        The execution is replayed from its own snapshot, never from the agent's current
        bindings, so publishing a new agent version mid-run cannot widen what that run may call.
        """

        snapshot = model.tool_grant or {}
        tools = snapshot.get("tools")
        allowed = (
            [str(tool.get("function_name")) for tool in tools] if isinstance(tools, list) else []
        )
        delegate_ids = snapshot.get("delegate_agent_ids")
        return AgentRunToolGrant(
            allowed_tool_names=allowed,
            allow_agent_delegation=bool(snapshot.get("allow_agent_delegation")),
            delegate_agent_ids=[UUID(str(x)) for x in delegate_ids]
            if isinstance(delegate_ids, list)
            else [],
        )

    async def _load_summary(self, *, tenant_id: UUID, agent_run_id: UUID) -> AgentRunSummary:
        model = await self.repository.get_agent_run(tenant_id=tenant_id, agent_run_id=agent_run_id)
        if model is None:
            raise NotFoundServiceException(message="agent_run_not_found")
        return AgentRunSummary(**self._summary_fields(model))

    @staticmethod
    def _summary_fields(model: AgentRunModel) -> dict[str, object]:
        return {
            "id": model.agent_run_id,
            "tenant_id": model.tenant_id,
            "agent_id": model.agent_id,
            "agent_version_id": model.agent_version_id,
            "origin": AgentRunOrigin(model.origin),
            "status": model.status,
            "canonical_status": model.canonical_status,
            "correlation_id": model.correlation_id,
            "node_run_id": model.node_run_id,
            "parent_agent_run_id": model.parent_agent_run_id,
            "root_agent_run_id": model.root_agent_run_id,
            "delegation_depth": int(model.delegation_depth or 0),
            "model": model.model,
            "max_iterations": model.max_iterations,
            "iterations_used": int(model.iterations_used or 0),
            "finish_reason": AgentRunFinishReason(model.finish_reason)
            if model.finish_reason
            else None,
            "input_tokens": model.input_tokens,
            "output_tokens": model.output_tokens,
            "estimated_cost": float(model.estimated_cost)
            if model.estimated_cost is not None
            else None,
            "started_at": model.started_at.isoformat() if model.started_at else None,
            "finished_at": model.finished_at.isoformat() if model.finished_at else None,
            "output": model.output or {},
            "error": model.error or {},
        }
