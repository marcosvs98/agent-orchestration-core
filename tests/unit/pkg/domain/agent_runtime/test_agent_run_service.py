"""Agent run lifecycle, including the A → B delegation scenario end to end.

Repositories are faked in memory; the runtime, grant resolution, dispatcher and delegation
service are the real ones, so what is exercised here is the wiring the HTTP layer depends on.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from domain.agents.services.a2a_delegation_service import A2ADelegationService
from domain.agents.services.a2a_translator import A2ATranslator
from domain.execution.schemas.agent_run import (
    DELEGATION_TOOL_NAME,
    AgentRunCreate,
    AgentRunFinishReason,
    AgentRunOrigin,
    AgentRunToolGrant,
)
from domain.execution.services.agent_run_service import AgentRunService
from domain.execution.services.agent_runtime.agent_loop import AgentCognitiveLoop
from domain.execution.services.agent_runtime.context_builder import AgentRunContextBuilder
from domain.execution.services.agent_runtime.tool_dispatcher import AgentToolDispatcher
from domain.execution.services.agent_runtime.tool_grant import ToolGrantResolver
from domain.execution.services.state_machine import AgentRunStatus
from domain.llm.schemas.agent_turn import (
    AgentToolCall,
    AgentTurnCompletion,
    AgentTurnStopReason,
)
from tests.unit.pkg.domain.agent_runtime.conftest import build_definition, build_tool


class _FakeAgentRunRepository:
    def __init__(self) -> None:
        self.runs: dict[UUID, SimpleNamespace] = {}
        self.messages: dict[UUID, list[dict]] = {}
        self.events: dict[UUID, list[dict]] = {}
        self.artifacts: dict[UUID, list[SimpleNamespace]] = {}

    async def create_agent_run(self, **kwargs) -> UUID:
        agent_run_id = uuid4()
        self.runs[agent_run_id] = SimpleNamespace(
            agent_run_id=agent_run_id,
            tenant_id=kwargs["tenant_id"],
            agent_id=kwargs["agent_id"],
            agent_version_id=kwargs["agent_version_id"],
            node_run_id=None,
            origin=kwargs["origin"].value,
            status=AgentRunStatus.CREATED.value,
            canonical_status=AgentRunStatus.CREATED.value,
            correlation_id=kwargs["correlation_id"],
            parent_agent_run_id=kwargs.get("parent_agent_run_id"),
            root_agent_run_id=kwargs.get("root_agent_run_id") or agent_run_id,
            delegation_depth=kwargs.get("delegation_depth", 0),
            model=kwargs["model"],
            max_iterations=kwargs["max_iterations"],
            iterations_used=0,
            finish_reason=None,
            input_tokens=None,
            output_tokens=None,
            estimated_cost=None,
            started_at=None,
            finished_at=None,
            input=kwargs["input_payload"],
            output={},
            error={},
            context_snapshot=kwargs["context_snapshot"],
            tool_grant=kwargs["tool_grant"],
        )
        self.messages[agent_run_id] = []
        self.events[agent_run_id] = []
        self.artifacts[agent_run_id] = []
        return agent_run_id

    async def get_agent_run(self, *, tenant_id: UUID, agent_run_id: UUID):
        run = self.runs.get(agent_run_id)
        if run is None or run.tenant_id != tenant_id:
            return None
        return run

    async def list_agent_runs(self, *, tenant_id: UUID, **kwargs) -> list:
        return [run for run in self.runs.values() if run.tenant_id == tenant_id]

    async def mark_running(self, *, agent_run_id: UUID) -> None:
        self.runs[agent_run_id].status = AgentRunStatus.RUNNING.value
        self.runs[agent_run_id].canonical_status = AgentRunStatus.RUNNING.value

    async def finish_agent_run(self, *, agent_run_id: UUID, **kwargs) -> None:
        run = self.runs[agent_run_id]
        run.status = kwargs["status"]
        run.canonical_status = kwargs["canonical_status"]
        run.output = kwargs["output"]
        run.error = kwargs["error"]
        run.finish_reason = kwargs["finish_reason"]
        run.iterations_used = kwargs["iterations_used"]
        run.input_tokens = kwargs["input_tokens"]
        run.output_tokens = kwargs["output_tokens"]
        run.estimated_cost = kwargs["estimated_cost"]

    async def append_message(self, *, agent_run_id: UUID, **kwargs) -> int:
        self.messages[agent_run_id].append(kwargs)
        return len(self.messages[agent_run_id])

    async def append_event(self, *, agent_run_id: UUID, **kwargs) -> int:
        self.events[agent_run_id].append(kwargs)
        return len(self.events[agent_run_id])

    async def append_artifact(self, *, agent_run_id: UUID, **kwargs) -> int:
        index = len(self.artifacts[agent_run_id]) + 1
        self.artifacts[agent_run_id].append(
            SimpleNamespace(
                artifact_index=index,
                name=kwargs["name"],
                description=kwargs["description"],
                parts=kwargs["parts"],
            )
        )
        return index

    async def list_messages(self, *, agent_run_id: UUID) -> list:
        return [
            SimpleNamespace(
                message_sequence=index + 1,
                role=message["role"],
                content=message.get("content"),
                tool_call_id=message.get("tool_call_id"),
                tool_name=message.get("tool_name"),
                trust_level=message.get("trust_level"),
                source=message.get("source"),
            )
            for index, message in enumerate(self.messages[agent_run_id])
        ]

    async def list_events(self, *, agent_run_id: UUID) -> list:
        return []

    async def list_artifacts(self, *, agent_run_id: UUID) -> list:
        return self.artifacts[agent_run_id]

    async def list_tool_runs(self, *, agent_run_id: UUID) -> list:
        return []


class _FakeDelegationRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def create_delegation(self, **kwargs) -> UUID:
        agent_delegation_id = uuid4()
        self.rows.append({"agent_delegation_id": agent_delegation_id, **kwargs})
        return agent_delegation_id

    async def update_delegation_result(self, **kwargs) -> None:
        for row in self.rows:
            if row["agent_delegation_id"] == kwargs["agent_delegation_id"]:
                row.update(kwargs)

    async def list_delegations_for_agent_run(self, *, parent_agent_run_id: UUID) -> list:
        return [
            SimpleNamespace(**row)
            for row in self.rows
            if row["parent_agent_run_id"] == parent_agent_run_id
        ]


def _idempotency() -> MagicMock:
    idempotency = MagicMock()
    idempotency.build_key = MagicMock(return_value="key")
    idempotency.try_acquire = AsyncMock(return_value=True)
    idempotency.get = AsyncMock(return_value=None)
    idempotency.set_result = AsyncMock()
    return idempotency


def _completion(text: str = "", tool_calls: list[AgentToolCall] | None = None):
    calls = tool_calls or []
    return AgentTurnCompletion(
        text=text,
        tool_calls=calls,
        stop_reason=AgentTurnStopReason.TOOL_CALLS if calls else AgentTurnStopReason.OUTPUT,
        token_usage={"input_tokens": 4, "output_tokens": 2},
        model_alias="gpt-4.1",
    )


def _build_service(tracer, tenant_id, *, definitions: dict[UUID, object], agent_llm):
    agent_run_repository = _FakeAgentRunRepository()
    delegation_repository = _FakeDelegationRepository()

    definition_resolver = MagicMock()
    definition_resolver.resolve = AsyncMock(
        side_effect=lambda *, tenant_id, agent_id: definitions[agent_id]
    )

    agents_repository = MagicMock()
    agents_repository.get_agent = AsyncMock(
        side_effect=lambda agent_id: MagicMock(agent_id=agent_id, tenant_id=tenant_id)
    )

    execution_repository = MagicMock()
    execution_repository.record_llm_usage = AsyncMock(return_value=uuid4())
    execution_repository.create_tool_run = AsyncMock(return_value=uuid4())

    tool_orchestrator = MagicMock()
    tool_orchestrator.execute_agent_tool_run = AsyncMock(
        return_value={"status_code": 200, "body": {"ok": True}}
    )

    translator = A2ATranslator()
    delegation_service = A2ADelegationService(
        repository=delegation_repository, translator=translator, tracer=tracer
    )
    dispatcher = AgentToolDispatcher(
        execution_repository=execution_repository,
        tool_orchestrator=tool_orchestrator,
        delegation_service=delegation_service,
        tracer=tracer,
    )
    loop = AgentCognitiveLoop(
        agent_llm=agent_llm,
        dispatcher=dispatcher,
        agent_run_repository=agent_run_repository,
        execution_repository=execution_repository,
        tracer=tracer,
    )
    service = AgentRunService(
        repository=agent_run_repository,
        delegation_repository=delegation_repository,
        definition_resolver=definition_resolver,
        grant_resolver=ToolGrantResolver(agents_repository=agents_repository),
        context_builder=AgentRunContextBuilder(),
        loop=loop,
        translator=translator,
        idempotency=_idempotency(),
        tracer=tracer,
    )
    return service, agent_run_repository, delegation_repository, tool_orchestrator


@pytest.mark.asyncio
async def test_a_run_executes_the_task_and_records_the_final_output(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="the answer"))
    service, repository, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )

    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(agent_id=definition.agent_id, instruction="answer"),
        wait=True,
    )

    assert summary.canonical_status == AgentRunStatus.COMPLETED.value
    assert summary.finish_reason is AgentRunFinishReason.FINAL_OUTPUT
    assert summary.origin is AgentRunOrigin.DIRECT
    assert repository.runs[summary.id].output == {"text": "the answer"}
    assert repository.artifacts[summary.id][0].name == "final-output"


@pytest.mark.asyncio
async def test_a_rejected_request_does_not_burn_the_idempotency_key(tracer, tenant_id) -> None:
    """A caller who fixes an invalid request must be able to retry the same key.

    The grant is resolved before the key is claimed, so a rejected tool name leaves the key free
    instead of answering 409 for the rest of its TTL.
    """

    definition = build_definition([build_tool("search")])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="ok"))
    service, _, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )

    from exceptions.service_exceptions import DomainValidationException

    with pytest.raises(DomainValidationException, match="tool_not_bound_to_agent_version"):
        await service.create_agent_run(
            tenant_id=tenant_id,
            principal_id="principal",
            endpoint="/core/v1/executions/agent-runs",
            idempotency_key="k1",
            request=AgentRunCreate(
                agent_id=definition.agent_id,
                instruction="answer",
                tools=AgentRunToolGrant(allowed_tool_names=["wire_transfer"]),
            ),
            wait=True,
        )

    service.idempotency.try_acquire.assert_not_awaited()

    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(
            agent_id=definition.agent_id,
            instruction="answer",
            tools=AgentRunToolGrant(allowed_tool_names=["search"]),
        ),
        wait=True,
    )
    assert summary.canonical_status == AgentRunStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_execution_context_is_frozen_on_the_run_not_on_the_agent(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="ok"))
    service, repository, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )

    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(
            agent_id=definition.agent_id,
            instruction="answer",
            context=[{"key": "ticket", "content": "customer is on the enterprise plan"}],
            tools=AgentRunToolGrant(allowed_tool_names=[]),
        ),
        wait=True,
    )

    snapshot = repository.runs[summary.id].context_snapshot
    assert snapshot["items"][0]["key"] == "ticket"
    request = agent_llm.complete_agent_turn.await_args.kwargs["request"]
    assert any("customer is on the enterprise plan" in (m.content or "") for m in request.messages)
    assert request.tools == []


@pytest.mark.asyncio
async def test_the_model_only_sees_the_tools_this_run_authorized(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search"), build_tool("book")])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="ok"))
    service, _, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )

    await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(
            agent_id=definition.agent_id,
            instruction="answer",
            tools=AgentRunToolGrant(allowed_tool_names=["search"]),
        ),
        wait=True,
    )

    request = agent_llm.complete_agent_turn.await_args.kwargs["request"]
    assert [tool.name for tool in request.tools] == ["search"]


@pytest.mark.asyncio
async def test_agent_a_delegates_to_agent_b_and_continues_with_its_result(
    tracer, tenant_id
) -> None:
    agent_a = build_definition([build_tool("search")])
    agent_b = build_definition([build_tool("summarise")])
    turns_by_model: dict[UUID, list] = {}

    agent_llm = MagicMock()
    calls: list = []

    async def _complete(*, request):
        calls.append(request)
        run_id = request.metadata["agent_run_id"]
        turns_by_model.setdefault(run_id, [])
        turns_by_model[run_id].append(request)
        is_delegator = any(tool.name == DELEGATION_TOOL_NAME for tool in request.tools)
        if is_delegator and len(turns_by_model[run_id]) == 1:
            return _completion(
                tool_calls=[
                    AgentToolCall(
                        call_id="d1",
                        name=DELEGATION_TOOL_NAME,
                        arguments={
                            "agent_id": str(agent_b.agent_id),
                            "instruction": "summarise the findings",
                        },
                    )
                ]
            )
        if is_delegator:
            return _completion(text="final answer built from B")
        return _completion(text="B's summary")

    agent_llm.complete_agent_turn = AsyncMock(side_effect=_complete)
    service, repository, delegation_repository, _ = _build_service(
        tracer,
        tenant_id,
        definitions={agent_a.agent_id: agent_a, agent_b.agent_id: agent_b},
        agent_llm=agent_llm,
    )

    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(
            agent_id=agent_a.agent_id,
            instruction="produce a report",
            tools=AgentRunToolGrant(
                allow_agent_delegation=True, delegate_agent_ids=[agent_b.agent_id]
            ),
        ),
        wait=True,
    )

    child_runs = [
        run for run in repository.runs.values() if run.origin == AgentRunOrigin.A2A_DELEGATION.value
    ]
    assert len(child_runs) == 1
    child = child_runs[0]

    assert summary.finish_reason is AgentRunFinishReason.FINAL_OUTPUT
    assert repository.runs[summary.id].output == {"text": "final answer built from B"}
    assert child.agent_id == agent_b.agent_id
    assert child.agent_run_id != summary.id
    assert child.parent_agent_run_id == summary.id
    assert child.root_agent_run_id == summary.id
    assert child.delegation_depth == 1
    assert child.canonical_status == AgentRunStatus.COMPLETED.value

    row = delegation_repository.rows[0]
    assert row["parent_agent_run_id"] == summary.id
    assert row["child_agent_run_id"] == child.agent_run_id
    assert row["a2a_task_state"] == "completed"

    detail = await service.get_agent_run(tenant_id=tenant_id, agent_run_id=summary.id)
    assert detail.delegations[0].child_agent_run_id == child.agent_run_id
    assert detail.delegations[0].target_agent_id == agent_b.agent_id


@pytest.mark.asyncio
async def test_a_run_is_not_visible_to_another_tenant(tracer, tenant_id) -> None:
    definition = build_definition([])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="ok"))
    service, _, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )
    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(agent_id=definition.agent_id, instruction="answer"),
        wait=True,
    )

    from exceptions.service_exceptions import NotFoundServiceException

    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await service.get_agent_run(tenant_id=uuid4(), agent_run_id=summary.id)


@pytest.mark.asyncio
async def test_a_terminal_run_cannot_be_cancelled(tracer, tenant_id) -> None:
    definition = build_definition([])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="ok"))
    service, _, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )
    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(agent_id=definition.agent_id, instruction="answer"),
        wait=True,
    )

    from exceptions.service_exceptions import ResourceBlockedServiceException

    with pytest.raises(ResourceBlockedServiceException, match="agent_run_not_cancellable"):
        await service.cancel_agent_run(tenant_id=tenant_id, agent_run_id=summary.id)


@pytest.mark.asyncio
async def test_async_submission_returns_before_the_run_finishes(tracer, tenant_id) -> None:
    definition = build_definition([])
    agent_llm = MagicMock()

    async def _never_finishing(*, request):
        await asyncio.sleep(3600)

    agent_llm.complete_agent_turn = AsyncMock(side_effect=_never_finishing)
    service, _, _, _ = _build_service(
        tracer, tenant_id, definitions={definition.agent_id: definition}, agent_llm=agent_llm
    )

    summary = await service.create_agent_run(
        tenant_id=tenant_id,
        principal_id="principal",
        endpoint="/core/v1/executions/agent-runs",
        idempotency_key="k1",
        request=AgentRunCreate(agent_id=definition.agent_id, instruction="answer"),
        wait=False,
    )

    assert summary.canonical_status in {
        AgentRunStatus.CREATED.value,
        AgentRunStatus.RUNNING.value,
    }

    cancelled = await service.cancel_agent_run(tenant_id=tenant_id, agent_run_id=summary.id)
    assert cancelled.canonical_status == AgentRunStatus.CANCELLED.value
    assert cancelled.finish_reason is AgentRunFinishReason.CANCELLED
