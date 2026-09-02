from __future__ import annotations

import json
from uuid import UUID

import jsonschema

from domain.agents.ports.agent_task_runner import AgentTaskRunnerPort
from domain.agents.schemas.a2a import A2ADelegationRequest
from domain.agents.services.a2a_delegation_service import A2ADelegationService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.agent_run import DELEGATION_TOOL_NAME
from domain.execution.services.agent_runtime.tool_grant import ResolvedToolGrant
from domain.execution.services.agent_runtime.types import (
    AgentRunScope,
    AgentToolCallStatus,
    ToolCallOutcome,
)
from domain.llm.schemas.agent_turn import AgentToolCall, AgentToolDefinition

_MAX_RESULT_TEXT_CHARS = 20000


class AgentToolDispatcher:
    """Turns a model-issued tool call into a real, authorized side effect.

    Every call is checked against the run's frozen grant before anything is created; a call the
    grant does not cover produces a denial the model can read and no ``tool_run`` at all.
    Delegation is dispatched here too, but as an A2A task with its own run, not as a function.
    """

    def __init__(
        self,
        execution_repository: ExecutionRepository,
        tool_orchestrator,
        delegation_service: A2ADelegationService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.execution_repository = execution_repository
        self.tool_orchestrator = tool_orchestrator
        self.delegation_service = delegation_service
        self.tracer = tracer

    def build_tool_definitions(self, grant: ResolvedToolGrant) -> list[AgentToolDefinition]:
        definitions = [
            AgentToolDefinition(
                name=tool.function_name,
                description=tool.description or tool.tool_name,
                parameters=tool.request_schema,
            )
            for tool in grant.tools
        ]
        if grant.allow_agent_delegation:
            definitions.append(self._delegation_tool_definition(grant))
        return definitions

    @staticmethod
    def _delegation_tool_definition(grant: ResolvedToolGrant) -> AgentToolDefinition:
        return AgentToolDefinition(
            name=DELEGATION_TOOL_NAME,
            description=(
                "Delegate a self-contained sub-task to another agent and wait for its result. "
                "Use it when the task needs a capability this agent does not have."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Identifier of the agent to delegate to.",
                        "enum": [str(agent_id) for agent_id in grant.delegate_agent_ids],
                    },
                    "instruction": {
                        "type": "string",
                        "description": "The task for the other agent, stated on its own.",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Structured input for the delegated task.",
                        "additionalProperties": True,
                    },
                },
                "required": ["agent_id", "instruction"],
                "additionalProperties": False,
            },
        )

    async def dispatch(
        self,
        *,
        scope: AgentRunScope,
        grant: ResolvedToolGrant,
        tool_call: AgentToolCall,
        runner: AgentTaskRunnerPort,
    ) -> ToolCallOutcome:
        if tool_call.name == DELEGATION_TOOL_NAME:
            return await self._dispatch_delegation(
                scope=scope, grant=grant, tool_call=tool_call, runner=runner
            )

        binding = grant.binding_for(tool_call.name)
        if binding is None:
            return self._denied(
                tool_call,
                reason="tool_not_authorized_for_this_run",
                detail={
                    "requested_tool": tool_call.name,
                    "authorized_tools": [tool.function_name for tool in grant.tools],
                },
            )

        try:
            jsonschema.validate(instance=tool_call.arguments, schema=binding.request_schema)
        except jsonschema.ValidationError as exc:
            return ToolCallOutcome(
                tool_call_id=tool_call.call_id,
                function_name=tool_call.name,
                status=AgentToolCallStatus.INVALID_ARGUMENTS,
                result_text=json.dumps(
                    {"error": "invalid_arguments", "detail": exc.message}, default=str
                ),
                tool_config_id=binding.tool_config_id,
                error={"error": "invalid_arguments", "detail": exc.message},
            )

        tool_run_id = await self.execution_repository.create_tool_run(
            tool_config_id=binding.tool_config_id,
            correlation_id=scope.correlation_id,
            agent_run_id=scope.agent_run_id,
            node_run_id=None,
            idempotency_key=f"{scope.agent_run_id}:{tool_call.call_id}",
            has_side_effect=True,
            input_payload=tool_call.arguments,
            tool_call_id=tool_call.call_id,
        )

        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.agent_runtime.execute_tool_call",
            input={
                "agent_run_id": str(scope.agent_run_id),
                "tool_run_id": str(tool_run_id),
                "function_name": tool_call.name,
            },
        ) as tool_span:
            try:
                result = await self.tool_orchestrator.execute_agent_tool_run(
                    tool_run_id=tool_run_id,
                    tenant_id=scope.tenant_id,
                    interaction_metadata=dict(scope.interaction_metadata),
                )
            except Exception as exc:
                if tool_span:
                    tool_span.error(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        output={"status": AgentToolCallStatus.ERROR.value},
                    )
                return ToolCallOutcome(
                    tool_call_id=tool_call.call_id,
                    function_name=tool_call.name,
                    status=AgentToolCallStatus.ERROR,
                    result_text=json.dumps(
                        {"error": "tool_execution_failed", "detail": type(exc).__name__}
                    ),
                    tool_run_id=tool_run_id,
                    tool_config_id=binding.tool_config_id,
                    error={"error": "tool_execution_failed", "detail": str(exc)},
                )
            if tool_span:
                tool_span.success(output={"status": AgentToolCallStatus.SUCCESS.value})

        return ToolCallOutcome(
            tool_call_id=tool_call.call_id,
            function_name=tool_call.name,
            status=AgentToolCallStatus.SUCCESS,
            result_text=self._result_text(result),
            tool_run_id=tool_run_id,
            tool_config_id=binding.tool_config_id,
            output=result,
        )

    async def _dispatch_delegation(
        self,
        *,
        scope: AgentRunScope,
        grant: ResolvedToolGrant,
        tool_call: AgentToolCall,
        runner: AgentTaskRunnerPort,
    ) -> ToolCallOutcome:
        raw_agent_id = str(tool_call.arguments.get("agent_id") or "")
        instruction = str(tool_call.arguments.get("instruction") or "").strip()
        payload = tool_call.arguments.get("payload")
        payload_dict = payload if isinstance(payload, dict) else {}

        if not grant.allow_agent_delegation:
            return self._denied(
                tool_call,
                reason="agent_delegation_not_authorized_for_this_run",
                detail={},
            )
        try:
            target_agent_id = UUID(raw_agent_id)
        except ValueError:
            return ToolCallOutcome(
                tool_call_id=tool_call.call_id,
                function_name=tool_call.name,
                status=AgentToolCallStatus.INVALID_ARGUMENTS,
                result_text=json.dumps({"error": "invalid_agent_id", "value": raw_agent_id}),
                error={"error": "invalid_agent_id", "value": raw_agent_id},
            )
        if not grant.is_delegation_allowed_for(target_agent_id):
            return self._denied(
                tool_call,
                reason="delegate_agent_not_authorized_for_this_run",
                detail={
                    "requested_agent_id": str(target_agent_id),
                    "authorized_agent_ids": [str(x) for x in grant.delegate_agent_ids],
                },
            )
        if not instruction:
            return ToolCallOutcome(
                tool_call_id=tool_call.call_id,
                function_name=tool_call.name,
                status=AgentToolCallStatus.INVALID_ARGUMENTS,
                result_text=json.dumps({"error": "instruction_required"}),
                error={"error": "instruction_required"},
            )

        try:
            outcome = await self.delegation_service.delegate(
                runner=runner,
                request=A2ADelegationRequest(
                    tenant_id=scope.tenant_id,
                    principal_id=scope.principal_id,
                    parent_agent_run_id=scope.agent_run_id,
                    root_agent_run_id=scope.root_agent_run_id,
                    delegation_depth=scope.delegation_depth,
                    correlation_id=scope.correlation_id,
                    target_agent_id=target_agent_id,
                    instruction=instruction,
                    payload=payload_dict,
                ),
            )
        except Exception as exc:
            return ToolCallOutcome(
                tool_call_id=tool_call.call_id,
                function_name=tool_call.name,
                status=AgentToolCallStatus.ERROR,
                result_text=json.dumps(
                    {"error": "delegation_failed", "detail": type(exc).__name__}
                ),
                error={"error": "delegation_failed", "detail": str(exc)},
            )

        return ToolCallOutcome(
            tool_call_id=tool_call.call_id,
            function_name=tool_call.name,
            status=AgentToolCallStatus.SUCCESS,
            result_text=self._result_text(
                {
                    "a2a_task_id": outcome.task.id,
                    "state": outcome.task.status.state.value,
                    "result": outcome.output_text,
                }
            ),
            output=outcome.task.model_dump(mode="json"),
            child_agent_run_id=outcome.child_agent_run_id,
            a2a_task_id=outcome.task.id,
            artifacts=list(outcome.task.artifacts),
        )

    @staticmethod
    def _denied(
        tool_call: AgentToolCall, *, reason: str, detail: dict[str, object]
    ) -> ToolCallOutcome:
        error = {"error": reason, **detail}
        return ToolCallOutcome(
            tool_call_id=tool_call.call_id,
            function_name=tool_call.name,
            status=AgentToolCallStatus.DENIED,
            result_text=json.dumps(error, default=str),
            error=error,
        )

    @staticmethod
    def _result_text(result: dict) -> str:
        text = json.dumps(result, default=str)
        if len(text) <= _MAX_RESULT_TEXT_CHARS:
            return text
        return text[:_MAX_RESULT_TEXT_CHARS] + '..."truncated"'
