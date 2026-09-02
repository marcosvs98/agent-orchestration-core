from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from adapters.observability.logging import get_logger
from domain.agents.ports.agent_task_runner import AgentTaskRunnerPort
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.agent_run_repository import AgentRunRepository
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.agent_run import AgentRunFinishReason
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.agent_runtime.context_builder import AgentRunPromptPart
from domain.execution.services.agent_runtime.definition import AgentDefinition
from domain.execution.services.agent_runtime.tool_dispatcher import AgentToolDispatcher
from domain.execution.services.agent_runtime.tool_grant import ResolvedToolGrant
from domain.execution.services.agent_runtime.types import (
    AgentRunScope,
    AgentToolCallStatus,
    ToolCallOutcome,
)
from domain.llm.ports.agent_llm import AgentLLMPort
from domain.llm.schemas.agent_turn import (
    AgentTurnMessage,
    AgentTurnRequest,
    AgentTurnRole,
)
from domain.llm.schemas.llm import LLMProviderType
from domain.llm.services.cost_engine import CostEngine
from exceptions.service_exceptions import DomainValidationException

logger = get_logger(__name__)


class AgentLoopResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    finish_reason: AgentRunFinishReason
    output_text: str = ""
    iterations_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float | None = None
    error: dict[str, object] = Field(default_factory=dict)
    tool_call_count: int = 0


class AgentCognitiveLoop:
    """Agent → context → LLM → tool call → tool result → LLM → … → final output.

    The loop is bounded by ``max_iterations``: a model that keeps asking for tools is stopped
    and the run finishes with ``MAX_ITERATIONS`` rather than spinning. Every turn and every tool
    result is written to the run's transcript before the next turn is requested, so a run that
    dies mid-flight leaves behind exactly what it had done.
    """

    def __init__(
        self,
        agent_llm: AgentLLMPort,
        dispatcher: AgentToolDispatcher,
        agent_run_repository: AgentRunRepository,
        execution_repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
        cost_engine: CostEngine | None = None,
    ) -> None:
        self.agent_llm = agent_llm
        self.dispatcher = dispatcher
        self.agent_run_repository = agent_run_repository
        self.execution_repository = execution_repository
        self.tracer = tracer
        self.cost_engine = cost_engine

    async def run(
        self,
        *,
        scope: AgentRunScope,
        definition: AgentDefinition,
        grant: ResolvedToolGrant,
        prompt_parts: list[AgentRunPromptPart],
        max_iterations: int,
        runner: AgentTaskRunnerPort,
    ) -> AgentLoopResult:
        messages = await self._seed_transcript(scope=scope, prompt_parts=prompt_parts)
        tool_definitions = self.dispatcher.build_tool_definitions(grant)

        input_tokens = 0
        output_tokens = 0
        cost = Decimal("0")
        tool_call_count = 0
        last_text = ""

        for iteration in range(1, max_iterations + 1):
            await self.agent_run_repository.append_event(
                agent_run_id=scope.agent_run_id,
                tenant_id=scope.tenant_id,
                event_type=ExecutionEventType.LLMCallStarted,
                payload={
                    "iteration": iteration,
                    "model": definition.model_name,
                    "tool_count": len(tool_definitions),
                    "message_count": len(messages),
                },
                correlation_id=scope.correlation_id,
            )
            try:
                with self.tracer.observe(
                    as_type="generation",
                    name="domain.execution.agent_runtime.turn",
                    input={
                        "agent_run_id": str(scope.agent_run_id),
                        "iteration": iteration,
                        "tool_count": len(tool_definitions),
                    },
                    model=definition.model_name,
                ) as generation_span:
                    completion = await self.agent_llm.complete_agent_turn(
                        request=AgentTurnRequest(
                            model_alias=definition.model_name,
                            messages=messages,
                            tools=tool_definitions,
                            principal_id=scope.principal_id,
                            metadata={"agent_run_id": str(scope.agent_run_id)},
                        )
                    )
                    if generation_span:
                        generation_span.success(
                            output={
                                "stop_reason": completion.stop_reason.value,
                                "tool_call_count": len(completion.tool_calls),
                                "content_length": len(completion.text),
                            },
                            usage_details=completion.token_usage,
                        )
            except DomainValidationException as exc:
                await self.agent_run_repository.append_event(
                    agent_run_id=scope.agent_run_id,
                    tenant_id=scope.tenant_id,
                    event_type=ExecutionEventType.LLMCallFailed,
                    payload={"iteration": iteration, "error": exc.message},
                    correlation_id=scope.correlation_id,
                )
                logger.exception(
                    "agent_run_llm_turn_failed",
                    agent_run_id=str(scope.agent_run_id),
                    iteration=iteration,
                )
                return AgentLoopResult(
                    finish_reason=AgentRunFinishReason.LLM_ERROR,
                    output_text=last_text,
                    iterations_used=iteration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=float(cost) if cost else None,
                    error={"error": exc.message, "detail": [str(e) for e in exc.errors()]},
                    tool_call_count=tool_call_count,
                )

            input_tokens += int(completion.token_usage.get("input_tokens", 0))
            output_tokens += int(completion.token_usage.get("output_tokens", 0))
            cost += await self._record_turn_usage(
                scope=scope, definition=definition, completion_usage=completion.token_usage
            )
            await self.agent_run_repository.append_event(
                agent_run_id=scope.agent_run_id,
                tenant_id=scope.tenant_id,
                event_type=ExecutionEventType.LLMCallCompleted,
                payload={
                    "iteration": iteration,
                    "stop_reason": completion.stop_reason.value,
                    "tool_call_count": len(completion.tool_calls),
                    "token_usage": completion.token_usage,
                },
                correlation_id=scope.correlation_id,
            )

            if completion.text:
                last_text = completion.text
            await self.agent_run_repository.append_message(
                agent_run_id=scope.agent_run_id,
                role=AgentTurnRole.ASSISTANT.value,
                content=completion.text or None,
                tool_calls=[call.model_dump(mode="json") for call in completion.tool_calls],
                source="llm_turn",
                provenance={"iteration": iteration},
            )
            messages = [
                *messages,
                AgentTurnMessage(
                    role=AgentTurnRole.ASSISTANT,
                    content=completion.text or None,
                    tool_calls=completion.tool_calls,
                ),
            ]

            if not completion.tool_calls:
                return AgentLoopResult(
                    finish_reason=AgentRunFinishReason.FINAL_OUTPUT,
                    output_text=last_text,
                    iterations_used=iteration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=float(cost) if cost else None,
                    tool_call_count=tool_call_count,
                )

            for tool_call in completion.tool_calls:
                tool_call_count += 1
                await self.agent_run_repository.append_event(
                    agent_run_id=scope.agent_run_id,
                    tenant_id=scope.tenant_id,
                    event_type=ExecutionEventType.ToolInvocationRequested,
                    payload={
                        "iteration": iteration,
                        "tool_call_id": tool_call.call_id,
                        "function_name": tool_call.name,
                    },
                    correlation_id=scope.correlation_id,
                )
                outcome = await self.dispatcher.dispatch(
                    scope=scope, grant=grant, tool_call=tool_call, runner=runner
                )
                await self._record_tool_outcome(scope=scope, iteration=iteration, outcome=outcome)
                await self.agent_run_repository.append_message(
                    agent_run_id=scope.agent_run_id,
                    role=AgentTurnRole.TOOL.value,
                    content=outcome.result_text,
                    tool_call_id=outcome.tool_call_id,
                    tool_name=outcome.function_name,
                    trust_level="tool_result",
                    source="tool_result",
                    provenance={
                        "iteration": iteration,
                        "status": outcome.status.value,
                        "tool_run_id": str(outcome.tool_run_id)
                        if outcome.tool_run_id is not None
                        else None,
                    },
                )
                messages = [
                    *messages,
                    AgentTurnMessage(
                        role=AgentTurnRole.TOOL,
                        content=outcome.result_text,
                        tool_call_id=outcome.tool_call_id,
                        tool_name=outcome.function_name,
                    ),
                ]

        return AgentLoopResult(
            finish_reason=AgentRunFinishReason.MAX_ITERATIONS,
            output_text=last_text,
            iterations_used=max_iterations,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=float(cost) if cost else None,
            error={"error": "max_iterations_reached", "max_iterations": max_iterations},
            tool_call_count=tool_call_count,
        )

    async def _seed_transcript(
        self, *, scope: AgentRunScope, prompt_parts: list[AgentRunPromptPart]
    ) -> list[AgentTurnMessage]:
        for part in prompt_parts:
            await self.agent_run_repository.append_message(
                agent_run_id=scope.agent_run_id,
                role=part.role.value,
                content=part.content,
                trust_level=part.trust_level.value,
                source=part.source,
                provenance=dict(part.provenance),
            )
        return [part.to_message() for part in prompt_parts]

    async def _record_tool_outcome(
        self, *, scope: AgentRunScope, iteration: int, outcome: ToolCallOutcome
    ) -> None:
        payload: dict[str, object] = {
            "iteration": iteration,
            "tool_call_id": outcome.tool_call_id,
            "function_name": outcome.function_name,
            "status": outcome.status.value,
            "tool_run_id": str(outcome.tool_run_id) if outcome.tool_run_id is not None else None,
        }
        if outcome.a2a_task_id is not None:
            payload["a2a_task_id"] = outcome.a2a_task_id
            payload["child_agent_run_id"] = (
                str(outcome.child_agent_run_id) if outcome.child_agent_run_id is not None else None
            )
            event_type = (
                ExecutionEventType.AgentDelegationCompleted
                if outcome.status == AgentToolCallStatus.SUCCESS
                else ExecutionEventType.AgentDelegationFailed
            )
        elif outcome.status == AgentToolCallStatus.DENIED:
            event_type = ExecutionEventType.ToolInvocationDenied
            payload["error"] = outcome.error
        elif outcome.status == AgentToolCallStatus.SUCCESS:
            event_type = ExecutionEventType.ToolInvocationSucceeded
        else:
            event_type = ExecutionEventType.ToolInvocationFailed
            payload["error"] = outcome.error
        await self.agent_run_repository.append_event(
            agent_run_id=scope.agent_run_id,
            tenant_id=scope.tenant_id,
            event_type=event_type,
            payload=payload,
            correlation_id=scope.correlation_id,
        )

    async def _record_turn_usage(
        self,
        *,
        scope: AgentRunScope,
        definition: AgentDefinition,
        completion_usage: dict[str, int],
    ) -> Decimal:
        """Put the turn in the same spend ledger as graph execution.

        Logged and swallowed on failure: accounting must not fail a turn whose side effects
        already happened, and the ledger is reconcilable from the run's events.
        """

        input_tokens = int(completion_usage.get("input_tokens", 0))
        output_tokens = int(completion_usage.get("output_tokens", 0))
        cost_usd: Decimal | None = None
        try:
            if self.cost_engine is not None:
                computed = await self.cost_engine.compute_cost(
                    provider=LLMProviderType.OPENAI.value,
                    provider_model=definition.model_name,
                    token_usage={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                )
                cost_usd = Decimal(str(computed)) if computed is not None else None
            await self.execution_repository.record_llm_usage(
                tenant_id=scope.tenant_id,
                flow_run_id=None,
                node_run_id=None,
                agent_run_id=scope.agent_run_id,
                session_id=None,
                provider=LLMProviderType.OPENAI.value,
                provider_model=definition.model_name,
                task_type="agent_run_turn",
                inference_layer="LLM",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=None,
            )
        except Exception:
            logger.exception(
                "agent_run_turn_usage_not_recorded",
                agent_run_id=str(scope.agent_run_id),
                tenant_id=str(scope.tenant_id),
            )
        return cost_usd or Decimal("0")
