from __future__ import annotations

from uuid import UUID

from domain.agents.ports.agent_task_runner import AgentTaskRunnerPort
from domain.agents.repositories.agent_delegation_repository import AgentDelegationRepository
from domain.agents.schemas.a2a import (
    A2ADelegationOutcome,
    A2ADelegationRequest,
    A2AMessage,
    A2ATaskExecution,
    A2ATaskState,
)
from domain.agents.services.a2a_translator import A2ATranslator
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import DomainValidationException

MAX_DELEGATION_DEPTH = 3


class A2ADelegationService:
    """Owns the lifecycle of one delegated A2A task.

    The delegated work is a task with its own identity and state, not a function call: the
    ``agent_delegation`` row survives the parent run and carries the correlation between the two
    executions even when the child fails.
    """

    def __init__(
        self,
        repository: AgentDelegationRepository,
        translator: A2ATranslator,
        tracer: RuntimeTracerPort,
        max_delegation_depth: int = MAX_DELEGATION_DEPTH,
    ) -> None:
        self.repository = repository
        self.translator = translator
        self.tracer = tracer
        self.max_delegation_depth = max_delegation_depth

    def assert_depth_allowed(self, delegation_depth: int) -> None:
        if delegation_depth >= self.max_delegation_depth:
            raise DomainValidationException(
                message="a2a_delegation_depth_exceeded",
                detail={
                    "delegation_depth": delegation_depth,
                    "max_delegation_depth": self.max_delegation_depth,
                },
            )

    async def delegate(
        self,
        *,
        runner: AgentTaskRunnerPort,
        request: A2ADelegationRequest,
    ) -> A2ADelegationOutcome:
        self.assert_depth_allowed(request.delegation_depth)

        task_id = self.translator.new_task_id()
        context_id = self.translator.context_id_for_root_run(request.root_agent_run_id)
        request_message = self.translator.build_request_message(
            task_id=task_id,
            context_id=context_id,
            instruction=request.instruction,
            payload=request.payload,
        )
        agent_delegation_id = await self.repository.create_delegation(
            tenant_id=request.tenant_id,
            parent_agent_run_id=request.parent_agent_run_id,
            target_agent_id=request.target_agent_id,
            transport="internal",
            remote_endpoint=None,
            a2a_task_id=task_id,
            a2a_context_id=context_id,
            a2a_task_state=A2ATaskState.SUBMITTED.value,
            request_message=request_message.model_dump(mode="json"),
            correlation_id=request.correlation_id,
        )

        execution = A2ATaskExecution(
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            target_agent_id=request.target_agent_id,
            task_id=task_id,
            context_id=context_id,
            message=request_message,
            parent_agent_run_id=request.parent_agent_run_id,
            root_agent_run_id=request.root_agent_run_id,
            delegation_depth=request.delegation_depth + 1,
            correlation_id=request.correlation_id,
            allowed_tool_names=request.allowed_tool_names,
            max_iterations=request.max_iterations,
        )

        with self.tracer.observe(
            as_type="chain",
            name="domain.agents.a2a.delegation.send_task",
            input={
                "a2a_task_id": task_id,
                "a2a_context_id": context_id,
                "target_agent_id": str(request.target_agent_id),
                "parent_agent_run_id": str(request.parent_agent_run_id),
                "delegation_depth": execution.delegation_depth,
            },
        ) as delegation_span:
            try:
                result = await runner.run_a2a_task(execution=execution)
            except Exception as exc:
                await self.repository.update_delegation_result(
                    agent_delegation_id=agent_delegation_id,
                    a2a_task_state=A2ATaskState.FAILED.value,
                    child_agent_run_id=None,
                    result={},
                    error={"type": type(exc).__name__, "message": str(exc)},
                    finished=True,
                )
                if delegation_span:
                    delegation_span.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"state": A2ATaskState.FAILED.value},
                    )
                raise

            status_message: A2AMessage | None = None
            if result.output_text:
                status_message = self.translator.build_agent_message(
                    task_id=task_id,
                    context_id=context_id,
                    text=result.output_text,
                )
            history = [request_message]
            if status_message is not None:
                history.append(status_message)
            task = self.translator.build_task(
                task_id=task_id,
                context_id=context_id,
                state=result.state,
                history=history,
                artifacts=list(result.artifacts),
                status_message=status_message,
                metadata={
                    "agent_delegation_id": str(agent_delegation_id),
                    "parent_agent_run_id": str(request.parent_agent_run_id),
                    "child_agent_run_id": str(result.child_agent_run_id)
                    if result.child_agent_run_id is not None
                    else None,
                },
            )
            await self.repository.update_delegation_result(
                agent_delegation_id=agent_delegation_id,
                a2a_task_state=result.state.value,
                child_agent_run_id=result.child_agent_run_id,
                result=task.model_dump(mode="json"),
                error=dict(result.error),
                finished=True,
            )
            if delegation_span:
                delegation_span.success(
                    output={
                        "state": result.state.value,
                        "child_agent_run_id": str(result.child_agent_run_id)
                        if result.child_agent_run_id is not None
                        else None,
                        "artifact_count": len(result.artifacts),
                    }
                )

        return A2ADelegationOutcome(
            agent_delegation_id=agent_delegation_id,
            task=task,
            child_agent_run_id=result.child_agent_run_id,
            output_text=result.output_text,
        )

    async def get_task(self, *, tenant_id: UUID, a2a_task_id: str) -> dict[str, object] | None:
        delegation = await self.repository.get_delegation_by_task_id(
            tenant_id=tenant_id, a2a_task_id=a2a_task_id
        )
        if delegation is None:
            return None
        result = delegation.result or {}
        if result:
            return dict(result)
        task = self.translator.build_task(
            task_id=delegation.a2a_task_id,
            context_id=delegation.a2a_context_id,
            state=A2ATaskState(delegation.a2a_task_state),
            history=[],
            artifacts=[],
        )
        return task.model_dump(mode="json")
