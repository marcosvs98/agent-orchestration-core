"""A2A delegation: agent B's work is a task with its own identity, not a function call.

Covers the correlation the orchestrator needs afterwards — the delegation row that outlives both
runs, and the A2A Task/Message/Artifact shapes that cross the boundary.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.agents.schemas.a2a import (
    A2ADelegationRequest,
    A2AArtifact,
    A2ARole,
    A2ATaskExecutionResult,
    A2ATaskState,
    A2ATextPart,
)
from domain.agents.services.a2a_delegation_service import A2ADelegationService
from domain.agents.services.a2a_translator import A2ATranslator
from exceptions.service_exceptions import DomainValidationException


def _service(tracer, *, max_depth: int = 3) -> tuple[A2ADelegationService, MagicMock]:
    repository = MagicMock()
    repository.create_delegation = AsyncMock(return_value=uuid4())
    repository.update_delegation_result = AsyncMock()
    service = A2ADelegationService(
        repository=repository,
        translator=A2ATranslator(),
        tracer=tracer,
        max_delegation_depth=max_depth,
    )
    return service, repository


def _request(tenant_id, *, depth: int = 0) -> A2ADelegationRequest:
    parent_run_id = uuid4()
    return A2ADelegationRequest(
        tenant_id=tenant_id,
        principal_id="principal",
        parent_agent_run_id=parent_run_id,
        root_agent_run_id=parent_run_id,
        delegation_depth=depth,
        correlation_id=uuid4(),
        target_agent_id=uuid4(),
        instruction="summarise the report",
        payload={"report_id": "r-1"},
    )


@pytest.mark.asyncio
async def test_delegation_produces_a_task_carrying_the_child_run_identity(
    tracer, tenant_id
) -> None:
    service, repository = _service(tracer)
    child_agent_run_id = uuid4()
    runner = MagicMock()
    runner.run_a2a_task = AsyncMock(
        return_value=A2ATaskExecutionResult(
            state=A2ATaskState.COMPLETED,
            child_agent_run_id=child_agent_run_id,
            output_text="summary text",
            artifacts=[
                A2AArtifact(artifact_id="a-1", name="final-output", parts=[A2ATextPart(text="s")])
            ],
        )
    )
    request = _request(tenant_id)

    outcome = await service.delegate(runner=runner, request=request)

    assert outcome.child_agent_run_id == child_agent_run_id
    assert outcome.task.status.state is A2ATaskState.COMPLETED
    assert outcome.task.context_id == request.root_agent_run_id.hex
    assert outcome.output_text == "summary text"
    assert outcome.task.artifacts[0].name == "final-output"


@pytest.mark.asyncio
async def test_the_delegation_record_correlates_both_executions(tracer, tenant_id) -> None:
    service, repository = _service(tracer)
    child_agent_run_id = uuid4()
    runner = MagicMock()
    runner.run_a2a_task = AsyncMock(
        return_value=A2ATaskExecutionResult(
            state=A2ATaskState.COMPLETED, child_agent_run_id=child_agent_run_id
        )
    )
    request = _request(tenant_id)

    await service.delegate(runner=runner, request=request)

    created = repository.create_delegation.await_args.kwargs
    assert created["parent_agent_run_id"] == request.parent_agent_run_id
    assert created["target_agent_id"] == request.target_agent_id
    assert created["a2a_task_state"] == A2ATaskState.SUBMITTED.value
    updated = repository.update_delegation_result.await_args.kwargs
    assert updated["child_agent_run_id"] == child_agent_run_id
    assert updated["a2a_task_state"] == A2ATaskState.COMPLETED.value
    assert updated["finished"] is True


@pytest.mark.asyncio
async def test_the_delegated_task_carries_the_instruction_as_an_a2a_message(
    tracer, tenant_id
) -> None:
    service, _ = _service(tracer)
    runner = MagicMock()
    runner.run_a2a_task = AsyncMock(
        return_value=A2ATaskExecutionResult(state=A2ATaskState.COMPLETED)
    )
    request = _request(tenant_id)

    await service.delegate(runner=runner, request=request)

    execution = runner.run_a2a_task.await_args.kwargs["execution"]
    assert execution.message.role is A2ARole.USER
    assert execution.message.text() == "summarise the report"
    assert execution.message.data() == {"report_id": "r-1"}
    assert execution.delegation_depth == request.delegation_depth + 1
    assert execution.parent_agent_run_id == request.parent_agent_run_id


@pytest.mark.asyncio
async def test_depth_is_bounded_so_delegation_cannot_recurse_without_end(tracer, tenant_id) -> None:
    service, repository = _service(tracer, max_depth=2)
    runner = MagicMock()
    runner.run_a2a_task = AsyncMock()

    with pytest.raises(DomainValidationException, match="a2a_delegation_depth_exceeded"):
        await service.delegate(runner=runner, request=_request(tenant_id, depth=2))

    repository.create_delegation.assert_not_awaited()
    runner.run_a2a_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failing_transport_leaves_a_failed_task_behind(tracer, tenant_id) -> None:
    service, repository = _service(tracer)
    runner = MagicMock()
    runner.run_a2a_task = AsyncMock(side_effect=RuntimeError("peer unreachable"))

    with pytest.raises(RuntimeError):
        await service.delegate(runner=runner, request=_request(tenant_id))

    updated = repository.update_delegation_result.await_args.kwargs
    assert updated["a2a_task_state"] == A2ATaskState.FAILED.value
    assert updated["error"]["type"] == "RuntimeError"


def test_a2a_objects_serialize_with_protocol_field_names() -> None:
    translator = A2ATranslator()
    message = translator.build_request_message(
        task_id="t-1", context_id="c-1", instruction="do it", payload={"k": "v"}
    )
    task = translator.build_task(
        task_id="t-1",
        context_id="c-1",
        state=A2ATaskState.COMPLETED,
        history=[message],
        artifacts=[
            translator.build_output_artifact(
                index=1, name="final-output", description=None, text="out"
            )
        ],
    )

    dumped = task.model_dump(mode="json")
    assert dumped["kind"] == "task"
    assert dumped["contextId"] == "c-1"
    assert dumped["status"]["state"] == "completed"
    assert dumped["history"][0]["messageId"]
    assert dumped["history"][0]["parts"][0]["kind"] == "text"
    assert dumped["history"][0]["parts"][1]["kind"] == "data"
    assert dumped["artifacts"][0]["artifactId"] == "final-output-1"


def test_run_status_maps_onto_a2a_task_state() -> None:
    translator = A2ATranslator()

    assert translator.task_state_for_run_status("RUNNING") is A2ATaskState.WORKING
    assert translator.task_state_for_run_status("COMPLETED") is A2ATaskState.COMPLETED
    assert translator.task_state_for_run_status("FAILED") is A2ATaskState.FAILED
    assert translator.task_state_for_run_status("CANCELLED") is A2ATaskState.CANCELED
    assert translator.task_state_for_run_status("something-else") is A2ATaskState.UNKNOWN
