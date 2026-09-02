"""Additional branch coverage for ExecutionService (mocked collaborators)."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from domain.common.schemas.versioning import VersionStatus
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.schemas.execution import (
    AgentRunCreate,
    FlowFailureReason,
    FlowRunCreate,
    FlowRunInput,
    FlowRunResumeInput,
    ToolRunCreate,
)
from domain.execution.schemas.trace import TraceContext
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.state_machine import (
    AgentRunStatus,
    FlowRunStatus,
    RunLifecycleStateMachine,
    RunStatus,
    ToolRunStatus,
)
from domain.governance.schemas.runtime_policy import (
    ResolvedRuntimePolicy,
    RuntimePolicyDefinition,
    RuntimePolicyScope,
    RuntimePolicySource,
)
from domain.rag.schemas.rag import RagCorpusKind
from exceptions.service_exceptions import (
    AIOutputValidationException,
    DomainConflictException,
    DomainValidationException,
    HashIncompatibleException,
    IdempotencyInProgressException,
    LimitExceededException,
    NotFoundServiceException,
    RagNotAllowedException,
    ResourceBlockedServiceException,
    SchemaIncompatibleException,
)
from pydantic import BaseModel, Field
from tests.unit.pkg.domain.execution.test_execution_service import TestExecutionService


class _TracerObserveWithHandles(TestExecutionService._FakeTracer):
    """observe() yields truthy handles so retriever/tool success branches run."""

    def __init__(self) -> None:
        self.observe_calls: list[tuple[str, MagicMock]] = []

    def observe(self, *, as_type, name, input, metadata=None):
        handle = MagicMock()
        self.observe_calls.append((name, handle))

        @contextlib.contextmanager
        def _cm():
            yield handle

        return _cm()

    def flow(self, *, trace=None, input=None):
        fh = MagicMock()

        @contextlib.contextmanager
        def _cm():
            yield fh

        return _cm()


class _TracerResumeRootObs(TestExecutionService._FakeTracer):
    def start_flow_trace(self, **kwargs):
        return TraceContext(
            trace_id=kwargs["trace_id"],
            flow_run_id=kwargs["flow_run_id"],
            tenant_id=kwargs["tenant_id"],
            session_id=kwargs.get("session_id"),
            user_id=kwargs.get("user_id"),
            root_observation_id="root-resume",
            flow_id=kwargs.get("flow_id"),
            flow_version_id=kwargs.get("flow_version_id"),
            interaction_id=kwargs.get("interaction_id"),
            correlation_id=kwargs.get("correlation_id"),
            channel=kwargs.get("channel"),
            external_message_id=kwargs.get("external_message_id"),
            graph_snapshot_id=kwargs.get("graph_snapshot_id"),
            execution_plan_hash=kwargs.get("execution_plan_hash"),
            flow_name=kwargs.get("flow_name"),
        )


def _execution_plan_json() -> dict:
    from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan

    return ExecutionPlan(
        start_node_id="a",
        ordered_nodes=["a"],
        adjacency_map={},
        terminal_nodes={"a"},
        structural_hash="h",
        nodes={"a": {}},
    ).model_dump(mode="json")


def _flow_run_orm_like(
    *,
    flow_run_id,
    flow_version_id,
    session_id=None,
    user_id: str = "u",
    correlation_id=None,
    trace_id=None,
    runtime_contract=None,
    status=None,
    canonical_status=None,
) -> SimpleNamespace:
    """Attributes expected by FlowRun.from_model (mirrors FlowRun ORM)."""
    if session_id is None:
        session_id = uuid4()
    if correlation_id is None:
        correlation_id = uuid4()
    if trace_id is None:
        trace_id = uuid4()
    if runtime_contract is None:
        runtime_contract = {}
    if status is None:
        status = RunStatus.RUNNING.value
    if canonical_status is None:
        canonical_status = FlowRunStatus.RUNNING.value
    return SimpleNamespace(
        flow_run_id=flow_run_id,
        origin_flow_run_id=None,
        flow_version_id=flow_version_id,
        session_id=session_id,
        user_id=user_id,
        interaction_id=None,
        correlation_id=correlation_id,
        status=status,
        canonical_status=canonical_status,
        started_at=None,
        finished_at=None,
        waiting_reason=None,
        waiting_deadline_at=None,
        input={},
        output={},
        error={},
        trace_id=trace_id,
        root_observation_id=None,
        temporal_workflow_id=None,
        temporal_run_id=None,
        flow_graph_snapshot_id=None,
        flow_snapshot_id=None,
        flow_deployment_id=None,
        runtime_contract=runtime_contract,
        execution_plan_hash=None,
        runtime_policy_hash=None,
        tool_catalog_hash=None,
        llm_provider_config_hash=None,
    )


def _minimal_graph_snapshot() -> dict[str, object]:
    compiled = EdgeEvaluator.compile_condition("1 == 1")
    return {
        "start_node": "a",
        "nodes": {
            "a": {"id": "a", "type": "IntentClassifier"},
            "b": {"id": "b", "type": "ResponseBuilder"},
        },
        "edges": [
            {
                "from_node": "a",
                "to_node": "b",
                "compiled_condition": compiled,
            }
        ],
    }


def _idempotency_mock() -> MagicMock:
    service = MagicMock(spec=IdempotencyService)
    service.build_key = MagicMock(return_value="test-key")
    service.try_acquire = AsyncMock(return_value=True)
    service.get = AsyncMock(return_value=None)
    service.set_result = AsyncMock()
    return service


def _base_repository() -> MagicMock:
    repo = MagicMock()
    repo.db = MagicMock()
    repo.cache_adapter = MagicMock()
    graph_snap_id = uuid4()
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(
        return_value=SimpleNamespace(
            graph_hash="test-graph-hash",
            flow_graph_snapshot_id=graph_snap_id,
            snapshot=_minimal_graph_snapshot(),
        )
    )
    repo.get_active_flow_deployment = AsyncMock(return_value=None)
    repo.get_flow_snapshot_by_id = AsyncMock(return_value=None)
    repo.get_flow_snapshot_by_flow_version = AsyncMock(return_value=None)
    repo.get_flow_graph_snapshot = AsyncMock(return_value=None)
    repo.get_graph_state = AsyncMock(return_value=None)
    repo.get_session = AsyncMock(return_value=None)
    repo.create_session = AsyncMock()
    repo.get_latest_waiting_flow_run_id = AsyncMock(return_value=(None, []))
    repo.acquire_flow_run_lock = AsyncMock()
    repo.end_event_batching = AsyncMock()
    repo.get_active_billing_policy_version_id = AsyncMock(return_value=uuid4())
    repo.create_flow_run = AsyncMock(return_value=uuid4())
    repo.merge_flow_run_runtime_contract = AsyncMock()
    repo.create_tool_run = AsyncMock(return_value=uuid4())
    repo.create_agent_run = AsyncMock(return_value=uuid4())
    repo.update_agent_run_result = AsyncMock()
    repo.create_interaction = AsyncMock(return_value=uuid4())
    repo.link_interaction_to_flow_run = AsyncMock()
    repo.get_flow_version = AsyncMock(return_value=SimpleNamespace(status="PUBLISHED"))
    repo.get_flow = AsyncMock(return_value=SimpleNamespace(tenant_id=uuid4(), name="f"))
    repo.get_active_flow_version_id = AsyncMock(return_value=uuid4())
    repo.get_tool_config = AsyncMock(
        return_value=SimpleNamespace(status="PUBLISHED", schema_version=None, config_hash=None)
    )
    repo.get_agent_run = AsyncMock(return_value=None)
    repo.get_agent_version = AsyncMock(return_value=None)
    repo.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    repo.get_ai_execution_policy_version = AsyncMock(return_value=None)
    repo.get_model = AsyncMock(return_value=None)
    repo.get_node_run = AsyncMock(return_value=None)
    repo.get_node = AsyncMock(return_value=None)
    repo.get_ai_task = AsyncMock(return_value=None)
    repo.append_execution_event = AsyncMock()
    repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=uuid4())
    repo.get_flow_run = AsyncMock(
        return_value=SimpleNamespace(
            session_id=uuid4(),
            output={},
            error={},
            status=RunStatus.CREATED.value,
            canonical_status=FlowRunStatus.CREATED.value,
            started_at=None,
            finished_at=None,
            root_observation_id=None,
            temporal_workflow_id=None,
            temporal_run_id=None,
        )
    )
    repo.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))
    repo.list_execution_events = AsyncMock(return_value=[])
    repo.set_root_observation_id = AsyncMock()
    repo.set_flow_run_status = AsyncMock()
    repo.start_event_batching = MagicMock()
    return repo


def _wire_service_defaults(svc: ExecutionService) -> None:
    svc.llm_executor = MagicMock()
    svc.runtime = MagicMock()
    svc.runtime.run = AsyncMock()
    svc.tools_service.list_available_tools_for_execution = AsyncMock(return_value=[])
    svc.cache_adapter.get = AsyncMock(return_value=None)
    svc.cache_adapter.set = AsyncMock()
    svc.hook.on_flow_start = AsyncMock()
    svc._rag_repository.get_rag_config = AsyncMock(return_value=None)
    resolved = ResolvedRuntimePolicy(
        source=RuntimePolicySource.DEFAULT,
        runtime_policy_id=None,
        version="1",
        definition=RuntimePolicyDefinition.model_validate(svc.default_policy["policy_definition"]),
        scope=RuntimePolicyScope.TENANT,
        flow_id=None,
    )
    svc.policy_resolver.resolve = AsyncMock(return_value=resolved)


def _make_service(
    repository: MagicMock,
    *,
    tracer=None,
    tools_service=None,
) -> ExecutionService:
    limits = MagicMock()
    limits.assert_can_create_agent_run = AsyncMock()
    limits.assert_can_create_tool_run = AsyncMock()
    svc = ExecutionService(
        repository=repository,
        idempotency=_idempotency_mock(),
        lifecycle=RunLifecycleStateMachine(),
        limits=limits,
        tracer=tracer or TestExecutionService._FakeTracer(),
        tools_service=tools_service,
    )
    _wire_service_defaults(svc)
    return svc


@pytest.mark.asyncio
async def test_init_accepts_injected_tools_service() -> None:
    repo = _base_repository()
    ts = MagicMock()
    svc = _make_service(repo, tools_service=ts)
    assert svc.tools_service is ts


@pytest.mark.asyncio
async def test_create_flow_run_requires_flow_selector() -> None:
    repo = _base_repository()
    svc = _make_service(repo)
    payload = FlowRunCreate.model_construct(
        session_id=uuid4(),
        user_id="u",
        flow_id=None,
        flow_version_id=None,
        input=FlowRunInput(user_input="x"),
    )
    with pytest.raises(DomainValidationException, match="flow_id_or_flow_version_id"):
        await svc.create_flow_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="k",
            flow_run=payload,
        )


@pytest.mark.asyncio
async def test_create_flow_run_flow_version_not_found() -> None:
    repo = _base_repository()
    repo.get_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_version_not_found"):
        await svc.create_flow_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=uuid4(),
                session_id=uuid4(),
                user_id="u",
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_invalid_user_id() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    payload = FlowRunCreate.model_construct(
        flow_version_id=fvid,
        session_id=uuid4(),
        user_id="   ",
        input=FlowRunInput(user_input="x"),
    )
    with pytest.raises(DomainValidationException, match="user_id_required"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=payload,
        )


@pytest.mark.asyncio
async def test_create_flow_run_wrong_tenant() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=uuid4(), name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_not_found"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_version_not_active() -> None:
    repo = _base_repository()
    tid, fid, fvid, other = uuid4(), uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = other
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="flow_version_not_active"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_idempotency_returns_cached() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    sid = uuid4()
    cid = uuid4()
    full_cached = {
        "id": str(uuid4()),
        "origin_flow_run_id": None,
        "flow_version_id": str(fvid),
        "session_id": str(sid),
        "user_id": "u",
        "interaction_id": None,
        "status": RunStatus.CREATED.value,
        "canonical_status": FlowRunStatus.CREATED.value,
        "correlation_id": str(cid),
        "started_at": None,
        "finished_at": None,
        "input": {},
        "output": {},
        "error": {},
        "trace_id": None,
        "root_observation_id": None,
        "flow_graph_snapshot_id": None,
        "flow_snapshot_id": None,
        "flow_deployment_id": None,
        "runtime_contract": {},
        "execution_plan_hash": None,
        "runtime_policy_hash": None,
        "tool_catalog_hash": None,
        "llm_provider_config_hash": None,
    }
    svc.idempotency.get = AsyncMock(return_value={"response": full_cached})
    out = await svc.create_flow_run(
        tenant_id=tid,
        endpoint="/e",
        idempotency_key="idem",
        flow_run=FlowRunCreate(
            flow_version_id=fvid,
            session_id=sid,
            user_id="u",
            input=FlowRunInput(user_input="x"),
            correlation_id=cid,
        ),
    )
    assert str(out.flow_version_id) == str(fvid)


@pytest.mark.asyncio
async def test_create_flow_run_idempotency_in_progress() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    svc.idempotency.get = AsyncMock(return_value={})
    with pytest.raises(IdempotencyInProgressException):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="idem",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_invalid_trace_id() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    with pytest.raises(DomainValidationException, match="invalid_trace_id"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
            ),
            trace_id="not-a-uuid",
        )


@pytest.mark.asyncio
async def test_create_flow_run_session_user_mismatch() -> None:
    repo = _base_repository()
    tid, fid, fvid, sid = uuid4(), uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    repo.get_session.return_value = SimpleNamespace(tenant_id=tid, user_id="other")
    svc = _make_service(repo)
    with pytest.raises(DomainConflictException, match="session_user_mismatch"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=sid,
                user_id="u",
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_with_deployment_and_nested_graph_snapshot() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    dep_id, fsnap_id, gsnap_nested = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    repo.get_active_flow_deployment = AsyncMock(
        return_value=SimpleNamespace(flow_snapshot_id=fsnap_id, flow_deployment_id=dep_id)
    )
    repo.get_flow_snapshot_by_id = AsyncMock(
        return_value=SimpleNamespace(
            flow_snapshot_id=fsnap_id,
            snapshot={"flow_graph_snapshot_id": str(gsnap_nested), "graph_hash": "gh"},
            runtime_policy={},
            tool_catalog={},
            llm_provider_config_hash=None,
            temporal_workflow_id=None,
            temporal_run_id=None,
            to_dict=lambda: {},
        )
    )
    nested = SimpleNamespace(
        graph_hash="nested-hash",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot = AsyncMock(return_value=nested)
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=nested)

    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=None)

    with patch.object(svc.plan_compiler, "compile") as compile_mock:
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k2",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )
    repo.get_flow_graph_snapshot.assert_awaited()
    compile_mock.assert_called_once()


@pytest.mark.asyncio
async def test_create_flow_run_legacy_graph_contract_branch() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    repo.get_flow_snapshot_by_id = AsyncMock(return_value=None)
    repo.get_flow_snapshot_by_flow_version = AsyncMock(return_value=None)
    g = SimpleNamespace(
        graph_hash="legacy-gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)

    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=None)
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="leg",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_cached_plan_path() -> None:
    repo = _base_repository()
    tid, fid, fvid = uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    svc = _make_service(repo)
    from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan

    plan = ExecutionPlan(
        start_node_id="a",
        ordered_nodes=["a"],
        adjacency_map={},
        terminal_nodes={"a"},
        structural_hash="test-structural-hash",
        nodes={"a": {}},
    )
    svc.cache_adapter.get = AsyncMock(return_value=plan.model_dump(mode="json"))
    with patch.object(svc.plan_compiler, "compile") as compile_mock:
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="cplan",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )
    compile_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_flow_run_runtime_marks_flow_error() -> None:
    repo = _base_repository()
    tid, fid, fvid, frid = uuid4(), uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    repo.create_flow_run = AsyncMock(return_value=frid)
    err_out = {"reason": "x"}
    repo.get_flow_run = AsyncMock(
        return_value=SimpleNamespace(
            flow_run_id=frid,
            session_id=uuid4(),
            output={"system_output": {}},
            error=err_out,
            status=RunStatus.FAILED.value,
            canonical_status=FlowRunStatus.FAILED.value,
            started_at=None,
            finished_at=None,
            root_observation_id=None,
            temporal_workflow_id=None,
            temporal_run_id=None,
        )
    )
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=None)
    fh = MagicMock()
    svc.tracer.flow = MagicMock(return_value=contextlib.nullcontext(fh))
    await svc.create_flow_run(
        tenant_id=tid,
        endpoint="/e",
        idempotency_key="err",
        flow_run=FlowRunCreate(
            flow_version_id=fvid,
            session_id=uuid4(),
            user_id="u",
            input=FlowRunInput(user_input="x"),
        ),
    )
    fh.error.assert_called_once()


@pytest.mark.asyncio
async def test_create_flow_run_sets_root_observation_when_trace_has_it() -> None:
    repo = _base_repository()
    tid, fid, fvid, frid = uuid4(), uuid4(), uuid4(), uuid4()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, flow_id=fid, to_dict=lambda: {}
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="x")
    repo.get_active_flow_version_id.return_value = fvid
    repo.create_flow_run = AsyncMock(return_value=frid)

    class TrWithRoot(TestExecutionService._FakeTracer):
        def start_flow_trace(self, **kwargs):
            return TraceContext(
                trace_id=kwargs["trace_id"],
                flow_run_id=kwargs["flow_run_id"],
                tenant_id=kwargs["tenant_id"],
                root_observation_id="obs-root",
            )

    svc = _make_service(repo, tracer=TrWithRoot())
    svc.cache_adapter.get = AsyncMock(return_value=None)
    await svc.create_flow_run(
        tenant_id=tid,
        endpoint="/e",
        idempotency_key="root",
        flow_run=FlowRunCreate(
            flow_version_id=fvid,
            session_id=uuid4(),
            user_id="u",
            input=FlowRunInput(user_input="x"),
        ),
    )
    repo.set_root_observation_id.assert_awaited()


@pytest.mark.asyncio
async def test_resume_flow_run_requires_payload() -> None:
    svc = _make_service(_base_repository())
    with pytest.raises(DomainValidationException, match="user_id_required"):
        await svc.resume_flow_run(
            flow_run_id=uuid4(),
            input_payload=None,
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_user_mismatch() -> None:
    repo = _base_repository()
    repo.get_flow_run = AsyncMock(
        return_value=SimpleNamespace(user_id="a", flow_version_id=uuid4())
    )
    svc = _make_service(repo)
    with pytest.raises(DomainConflictException, match="session_user_mismatch"):
        await svc.resume_flow_run(
            flow_run_id=uuid4(),
            input_payload=FlowRunResumeInput(user_id="b"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_compiles_plan_when_cache_miss() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid)
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    g = SimpleNamespace(
        graph_hash="gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=None)
    with patch.object(
        svc.plan_compiler, "compile", wraps=svc.plan_compiler.compile
    ) as compile_mock:
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )
    compile_mock.assert_called_once()


@pytest.mark.asyncio
async def test_resume_flow_run_invalid_graph_state_snapshot() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid)
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": []}))
    g = SimpleNamespace(
        graph_hash="gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=None)
    with pytest.raises(DomainValidationException, match="invalid_graph_state"):
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_create_agent_run_limit_exceeded_emits_event() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_flow_run.return_value = SimpleNamespace(session_id=uuid4())
    svc = _make_service(repo)

    async def boom(**_kwargs):
        raise LimitExceededException(message="limit")

    svc.limits.assert_can_create_agent_run = boom
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id.return_value = av_id
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    with pytest.raises(LimitExceededException):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="a",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )
    repo.append_execution_event.assert_awaited()


@pytest.mark.asyncio
async def test_create_agent_run_rag_tenant_denied() -> None:
    repo = _base_repository()
    tenant_id = uuid4()
    frid = uuid4()
    rcid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=rcid,
        allow_session_context=False,
        allow_memory_write=False,
    )
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=rcid,
        ai_execution_policy_version_id=pol_id,
        system_prompt="hi",
    )
    repo.get_active_agent_version_id.return_value = av_id
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    svc = _make_service(repo)
    svc._rag_repository.get_rag_config = AsyncMock(
        return_value=SimpleNamespace(
            tenant_id=tenant_id, corpus_kind=RagCorpusKind.TENANT_KNOWLEDGE
        )
    )
    with pytest.raises(RagNotAllowedException):
        await svc.create_agent_run(
            tenant_id=tenant_id,
            endpoint="/e",
            idempotency_key="r",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


class _OutSchema(BaseModel):
    answer: str = Field(min_length=1)


@pytest.mark.asyncio
async def test_complete_agent_run_validation_error_path() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    nrid = uuid4()
    frid = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(
        agent_run_id=ar_id,
        node_run_id=nrid,
        agent_version_id=uuid4(),
        correlation_id=uuid4(),
        model="m",
        runtime_snapshot={"ai_execution_policy_version_id": str(uuid4())},
        runtime_snapshot_hash="h",
        input={},
    )
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=frid)
    svc = _make_service(repo)
    with pytest.raises(AIOutputValidationException):
        await svc.complete_agent_run(
            agent_run_id=ar_id,
            raw_output={},
            output_schema=_OutSchema,
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_agent_limit_exceeded() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
    svc = _make_service(repo)

    async def boom(**_kwargs):
        raise LimitExceededException(message="tl")

    svc.limits.assert_can_create_tool_run = boom
    repo.get_flow_run.return_value = SimpleNamespace(session_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, schema_version=None, config_hash=None
    )
    with pytest.raises(LimitExceededException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="t",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_hash_prefix_mismatch() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, schema_version=1, config_hash="zzz"
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        supported_tool_schema_version=1,
        supported_tool_config_hash_prefix="aa",
    )
    svc = _make_service(repo)
    with pytest.raises(HashIncompatibleException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="h",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_get_flow_run_failure_reason_from_event() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_flow_run.return_value = _flow_run_orm_like(
        flow_run_id=frid,
        flow_version_id=uuid4(),
        status=RunStatus.FAILED.value,
        canonical_status=FlowRunStatus.FAILED.value,
    )
    ev = SimpleNamespace(
        type=ExecutionEventType.FlowFailed,
        payload={"reason": "POLICY_VIOLATION"},
    )
    repo.list_execution_events = AsyncMock(return_value=[ev])
    svc = _make_service(repo)
    out = await svc.get_flow_run(str(frid))
    assert out.failure_reason is FlowFailureReason.POLICY_VIOLATION


@pytest.mark.asyncio
async def test_list_execution_events_maps_rows() -> None:
    repo = _base_repository()
    eid = uuid4()
    repo.list_execution_events = AsyncMock(
        return_value=[
            SimpleNamespace(
                execution_event_id=eid,
                tenant_id=uuid4(),
                user_id="u",
                session_id=uuid4(),
                flow_run_id=uuid4(),
                type="X",
                occurred_at=datetime.now(timezone.utc),
                event_sequence=1,
                correlation_id=uuid4(),
                causation_id=None,
                schema_version=1,
                payload={},
            )
        ]
    )
    svc = _make_service(repo)
    out = await svc.list_execution_events(tenant_id=uuid4(), flow_run_id=uuid4(), limit=5)
    assert len(out) == 1
    assert str(out[0].id) == str(eid)


def _repo_happy_create_flow(tid, fvid, fid) -> MagicMock:
    repo = _base_repository()
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        flow_id=fid,
        to_dict=lambda: {"flow_version_id": str(fvid)},
    )
    repo.get_flow.return_value = SimpleNamespace(tenant_id=tid, name="flow")
    repo.get_active_flow_version_id.return_value = fvid
    return repo


@pytest.mark.asyncio
async def test_create_flow_run_agent_observe_success_called() -> None:
    tid, fvid, fid = uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    tr = _TracerObserveWithHandles()
    svc = _make_service(repo, tracer=tr)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="obs",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )
    select = next(
        (h for n, h in tr.observe_calls if "select_flow_version_and_path" in n),
        None,
    )
    assert select is not None
    select.success.assert_called()


@pytest.mark.asyncio
async def test_create_flow_run_flow_id_required_when_version_missing_flow_id() -> None:
    tid, fvid, fid = uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_flow_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        flow_id=None,
        to_dict=lambda: {},
    )
    svc = _make_service(repo)
    with pytest.raises(DomainValidationException, match="flow_id_required"):
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="k",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_get_latest_waiting_when_correlation_only() -> None:
    tid, fvid, fid, sid, cid = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_latest_waiting_flow_run_id = AsyncMock(return_value=(None, []))
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="corr",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=sid,
                user_id="u",
                input=FlowRunInput(user_input="x"),
                correlation_id=cid,
            ),
        )
    repo.get_latest_waiting_flow_run_id.assert_awaited()


@pytest.mark.asyncio
async def test_create_flow_run_origin_waiting_invalid_graph_state() -> None:
    tid, fvid, fid, sid, cid, origin_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_latest_waiting_flow_run_id = AsyncMock(return_value=(origin_id, []))

    async def _gf(rid):
        if rid == origin_id:
            return SimpleNamespace(
                flow_run_id=origin_id,
                status=RunStatus.WAITING_INPUT.value,
                canonical_status=FlowRunStatus.WAITING.value,
                session_id=sid,
                output={},
                error={},
                started_at=None,
                finished_at=None,
                root_observation_id=None,
                temporal_workflow_id=None,
                temporal_run_id=None,
            )
        return _flow_run_orm_like(flow_run_id=rid, flow_version_id=fvid)

    repo.get_flow_run = AsyncMock(side_effect=_gf)
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": []}))
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        with pytest.raises(DomainValidationException, match="invalid_graph_state"):
            await svc.create_flow_run(
                tenant_id=tid,
                endpoint="/e",
                idempotency_key="og",
                flow_run=FlowRunCreate(
                    flow_version_id=fvid,
                    session_id=sid,
                    user_id="u",
                    input=FlowRunInput(user_input="x"),
                    correlation_id=cid,
                ),
            )


@pytest.mark.asyncio
async def test_create_flow_run_origin_waiting_no_graph_state_clears_origin() -> None:
    tid, fvid, fid, sid, cid, origin_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_latest_waiting_flow_run_id = AsyncMock(return_value=(origin_id, []))

    async def _gf(rid):
        if rid == origin_id:
            return SimpleNamespace(
                flow_run_id=origin_id,
                status=RunStatus.WAITING_INPUT.value,
                canonical_status=FlowRunStatus.WAITING.value,
                session_id=sid,
                output={},
                error={},
                started_at=None,
                finished_at=None,
                root_observation_id=None,
                temporal_workflow_id=None,
                temporal_run_id=None,
            )
        return _flow_run_orm_like(flow_run_id=rid, flow_version_id=fvid)

    repo.get_flow_run = AsyncMock(side_effect=_gf)
    repo.get_graph_state = AsyncMock(return_value=None)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="ogn",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=sid,
                user_id="u",
                input=FlowRunInput(user_input="x"),
                correlation_id=cid,
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_origin_not_waiting_clears_origin() -> None:
    tid, fvid, fid, sid, cid, origin_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_latest_waiting_flow_run_id = AsyncMock(return_value=(origin_id, []))

    async def _gf(rid):
        if rid == origin_id:
            return SimpleNamespace(
                flow_run_id=origin_id,
                status=RunStatus.RUNNING.value,
                canonical_status=FlowRunStatus.RUNNING.value,
                session_id=sid,
                output={},
                error={},
                started_at=None,
                finished_at=None,
                root_observation_id=None,
                temporal_workflow_id=None,
                temporal_run_id=None,
            )
        return _flow_run_orm_like(flow_run_id=rid, flow_version_id=fvid)

    repo.get_flow_run = AsyncMock(side_effect=_gf)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="onw",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=sid,
                user_id="u",
                input=FlowRunInput(user_input="x"),
                correlation_id=cid,
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_flow_snapshot_required_when_legacy_off() -> None:
    tid, fvid, fid = uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_flow_snapshot_by_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = False
        mock_settings.TEMPORAL_ENABLED = False
        with pytest.raises(ResourceBlockedServiceException, match="flow_snapshot_required"):
            await svc.create_flow_run(
                tenant_id=tid,
                endpoint="/e",
                idempotency_key="snap",
                flow_run=FlowRunCreate(
                    flow_version_id=fvid,
                    session_id=uuid4(),
                    user_id="u",
                    input=FlowRunInput(user_input="x"),
                ),
            )


@pytest.mark.asyncio
async def test_create_flow_run_legacy_missing_graph_snapshot() -> None:
    tid, fvid, fid = uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        with pytest.raises(ResourceBlockedServiceException, match="flow_graph_snapshot_missing"):
            await svc.create_flow_run(
                tenant_id=tid,
                endpoint="/e",
                idempotency_key="legg",
                flow_run=FlowRunCreate(
                    flow_version_id=fvid,
                    session_id=uuid4(),
                    user_id="u",
                    input=FlowRunInput(user_input="x"),
                ),
            )


@pytest.mark.asyncio
async def test_create_flow_run_cache_handles_and_runtime_success_paths() -> None:
    tid, fvid, fid, frid = uuid4(), uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.create_flow_run = AsyncMock(return_value=frid)
    repo.get_flow_run = AsyncMock(
        return_value=SimpleNamespace(
            flow_run_id=frid,
            session_id=uuid4(),
            output={"system_output": {"ok": True}},
            error={},
            status=RunStatus.COMPLETED.value,
            canonical_status=FlowRunStatus.COMPLETED.value,
            started_at=None,
            finished_at=None,
            root_observation_id=None,
            temporal_workflow_id=None,
            temporal_run_id=None,
        )
    )
    svc = _make_service(repo, tracer=_TracerObserveWithHandles())
    svc.cache_adapter.get = AsyncMock(return_value=None)
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = True
        mock_settings.TEMPORAL_ENABLED = False
        mock_settings.CACHE_SILENT_MODE = True
        mock_settings.EMBEDDING_DIMENSION = 1536
        mock_settings.OPENAI_API_KEY = "k"
        await svc.create_flow_run(
            tenant_id=tid,
            endpoint="/e",
            idempotency_key="succ",
            flow_run=FlowRunCreate(
                flow_version_id=fvid,
                session_id=uuid4(),
                user_id="u",
                input=FlowRunInput(user_input="x"),
            ),
        )


@pytest.mark.asyncio
async def test_resume_flow_run_not_found() -> None:
    repo = _base_repository()
    repo.get_flow_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
        await svc.resume_flow_run(
            flow_run_id=uuid4(),
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_graph_state_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=uuid4(), user_id="u")
    )
    repo.get_graph_state = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="graph_state_not_found"):
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_flow_version_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    repo.get_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_version_not_found"):
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_snapshot_branch_policy_resolve_when_snapshot_missing() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    fsnap_id = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(
            flow_run_id=frid,
            flow_version_id=fvid,
            runtime_contract={"flow_snapshot_id": str(fsnap_id)},
        )
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    repo.get_flow_snapshot_by_id = AsyncMock(return_value=None)
    g = SimpleNamespace(
        graph_hash="gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    await svc.resume_flow_run(
        flow_run_id=frid,
        input_payload=FlowRunResumeInput(user_id="u"),
        channel="http",
        headers={},
        external_message_id=None,
        request_id=None,
        trace_id=None,
    )
    svc.policy_resolver.resolve.assert_awaited()


@pytest.mark.asyncio
async def test_resume_flow_run_flow_snapshot_loads_nested_graph() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    fsnap_id = uuid4()
    nested_gs = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(
            flow_run_id=frid,
            flow_version_id=fvid,
            runtime_contract={"flow_snapshot_id": str(fsnap_id)},
        )
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    nested = SimpleNamespace(
        graph_hash="nested",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_snapshot_by_id = AsyncMock(
        return_value=SimpleNamespace(
            snapshot={"flow_graph_snapshot_id": str(nested_gs), "graph_hash": "x"},
            runtime_policy={},
            tool_catalog={},
            to_dict=lambda: {},
        )
    )
    repo.get_flow_graph_snapshot = AsyncMock(return_value=nested)
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    await svc.resume_flow_run(
        flow_run_id=frid,
        input_payload=FlowRunResumeInput(user_id="u"),
        channel="http",
        headers={},
        external_message_id=None,
        request_id=None,
        trace_id=None,
    )
    repo.get_flow_graph_snapshot.assert_awaited()


@pytest.mark.asyncio
async def test_resume_flow_run_graph_snapshot_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid)
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_graph_snapshot_not_found"):
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_resume_flow_run_sets_root_observation_when_trace_has_it() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        return_value=_flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid)
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    g = SimpleNamespace(
        graph_hash="gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)
    svc = _make_service(repo, tracer=_TracerResumeRootObs())
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    await svc.resume_flow_run(
        flow_run_id=frid,
        input_payload=FlowRunResumeInput(user_id="u"),
        channel="http",
        headers={},
        external_message_id=None,
        request_id=None,
        trace_id=None,
    )
    repo.set_root_observation_id.assert_awaited()


@pytest.mark.asyncio
async def test_resume_flow_run_missing_after_runtime_raises() -> None:
    repo = _base_repository()
    frid = uuid4()
    fvid = uuid4()
    repo.get_flow_run = AsyncMock(
        side_effect=[
            _flow_run_orm_like(flow_run_id=frid, flow_version_id=fvid),
            None,
        ]
    )
    repo.get_flow_version = AsyncMock(
        return_value=SimpleNamespace(flow_id=uuid4(), flow_version_id=fvid)
    )
    repo.get_graph_state = AsyncMock(return_value=SimpleNamespace(state={"current_node_id": "a"}))
    g = SimpleNamespace(
        graph_hash="gh",
        flow_graph_snapshot_id=uuid4(),
        snapshot=_minimal_graph_snapshot(),
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=g)
    svc = _make_service(repo)
    svc.cache_adapter.get = AsyncMock(return_value=_execution_plan_json())
    with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
        await svc.resume_flow_run(
            flow_run_id=frid,
            input_payload=FlowRunResumeInput(user_id="u"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )


@pytest.mark.asyncio
async def test_create_agent_run_node_run_not_found() -> None:
    repo = _base_repository()
    repo.get_node_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="a",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=uuid4(),
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_limit_re_raises_when_flow_run_missing() -> None:
    repo = _base_repository()
    nrid, frid = uuid4(), uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)

    async def _lim(**_k):
        raise LimitExceededException(message="cap")

    svc = _make_service(repo)
    svc.limits.assert_can_create_agent_run = _lim
    repo.get_flow_run = AsyncMock(return_value=None)
    with pytest.raises(LimitExceededException):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="l",
            agent_run=AgentRunCreate(
                node_run_id=nrid,
                agent_version_id=uuid4(),
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_node_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="node_not_found"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="n",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=uuid4(),
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_agent_version_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="agent_version_not_found"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="av",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=uuid4(),
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_agent_version_blocked() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.DRAFT,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=uuid4(),
        system_prompt="",
    )
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="agent_version_blocked"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="ab",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=uuid4(),
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_agent_version_not_active() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=uuid4(),
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=uuid4())
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="agent_version_not_active"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="na",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_no_ai_policy_on_agent_version() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=None,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="ai_execution_policy_not_active"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="np",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_policy_version_not_found() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="ai_execution_policy_version_not_found"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="pv",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_policy_version_blocked() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.DRAFT, model_id=mid
    )
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="ai_execution_policy_blocked"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="pb",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_rag_user_memory_denied() -> None:
    repo = _base_repository()
    tenant_id = uuid4()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    rcid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=rcid,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=rcid,
        ai_execution_policy_version_id=pol_id,
        system_prompt="x",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    svc = _make_service(repo)
    svc._rag_repository.get_rag_config = AsyncMock(
        return_value=SimpleNamespace(tenant_id=tenant_id, corpus_kind=RagCorpusKind.USER_MEMORY)
    )
    with pytest.raises(RagNotAllowedException):
        await svc.create_agent_run(
            tenant_id=tenant_id,
            endpoint="/e",
            idempotency_key="um",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_billing_policy_not_active() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="s",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    repo.get_active_billing_policy_version_id = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="billing_policy_not_active"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="bill",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_idempotency_returns_cached() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    bp = uuid4()
    cid = uuid4()
    ar_id = uuid4()
    nrid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    cached = {
        "id": str(ar_id),
        "node_run_id": str(nrid),
        "agent_version_id": str(av_id),
        "billing_policy_version_id": str(bp),
        "model": "m",
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost": None,
        "status": RunStatus.CREATED.value,
        "canonical_status": AgentRunStatus.CREATED.value,
        "correlation_id": str(cid),
        "started_at": None,
        "finished_at": None,
        "input": {},
        "output": {},
        "error": {},
        "system_prompt_hash": None,
        "runtime_snapshot": {},
        "runtime_snapshot_hash": None,
    }
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    svc.idempotency.get = AsyncMock(return_value={"response": cached})
    out = await svc.create_agent_run(
        tenant_id=uuid4(),
        endpoint="/e",
        idempotency_key="idem",
        agent_run=AgentRunCreate(
            node_run_id=nrid,
            agent_version_id=av_id,
            input={},
            correlation_id=cid,
        ),
    )
    assert str(out.id) == str(ar_id)


@pytest.mark.asyncio
async def test_create_agent_run_flow_run_missing_after_create() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")

    async def _gf(_fid):
        return None

    repo.get_flow_run = AsyncMock(side_effect=_gf)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="gf",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


class _CompleteSchema(BaseModel):
    answer: str = "ok"


class _StrictAnswerSchema(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_complete_agent_run_not_found() -> None:
    repo = _base_repository()
    repo.get_agent_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await svc.complete_agent_run(
            agent_run_id=uuid4(),
            raw_output={},
            output_schema=_CompleteSchema,
        )


@pytest.mark.asyncio
async def test_complete_agent_run_validation_fails_without_node_run() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(
        agent_run_id=ar_id,
        node_run_id=uuid4(),
        agent_version_id=uuid4(),
        correlation_id=uuid4(),
        model="m",
        runtime_snapshot={"ai_execution_policy_version_id": str(uuid4())},
        runtime_snapshot_hash="h",
        input={},
    )
    repo.get_node_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(DomainValidationException, match="node_run_not_found"):
        await svc.complete_agent_run(
            agent_run_id=ar_id,
            raw_output={},
            output_schema=_StrictAnswerSchema,
        )


@pytest.mark.asyncio
async def test_complete_agent_run_success_but_node_run_missing_after_update() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(
        agent_run_id=ar_id,
        node_run_id=uuid4(),
        agent_version_id=uuid4(),
        correlation_id=uuid4(),
        model="m",
        runtime_snapshot={"ai_execution_policy_version_id": str(uuid4())},
        runtime_snapshot_hash="h",
        input={},
    )
    repo.get_node_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(DomainValidationException, match="node_run_not_found"):
        await svc.complete_agent_run(
            agent_run_id=ar_id,
            raw_output={"answer": "yes"},
            output_schema=_CompleteSchema,
        )


@pytest.mark.asyncio
async def test_create_tool_run_billing_policy_not_active() -> None:
    repo = _base_repository()
    repo.get_active_billing_policy_version_id = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="billing_policy_not_active"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="b",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_node_limit_raises_when_no_flow_run() -> None:
    repo = _base_repository()
    nrid = uuid4()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)

    async def _lim(**_k):
        raise LimitExceededException(message="x")

    svc = _make_service(repo)
    svc.limits.assert_can_create_tool_run = _lim
    repo.get_flow_run = AsyncMock(return_value=None)
    with pytest.raises(LimitExceededException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="tl",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=nrid,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_agent_limit_raises_when_no_flow_run() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())

    async def _lim(**_k):
        raise LimitExceededException(message="x")

    svc = _make_service(repo)
    svc.limits.assert_can_create_tool_run = _lim
    repo.get_flow_run = AsyncMock(return_value=None)
    with pytest.raises(LimitExceededException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="ta",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_agent_agent_run_not_found() -> None:
    repo = _base_repository()
    repo.get_agent_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="anf",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_agent_node_run_not_found() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="nnf",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_tool_config_not_found() -> None:
    repo = _base_repository()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=uuid4())
    repo.get_tool_config = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="tool_config_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="tc",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_tool_config_blocked() -> None:
    repo = _base_repository()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.DRAFT, schema_version=None, config_hash=None
    )
    svc = _make_service(repo)
    with pytest.raises(ResourceBlockedServiceException, match="tool_config_blocked"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="tb",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_agent_path_agent_version_not_found() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, schema_version=1, config_hash="abc"
    )
    repo.get_agent_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="agent_version_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="avn",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_schema_mismatch() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run.return_value = SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4())
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, schema_version=2, config_hash="abc"
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        supported_tool_schema_version=1,
        supported_tool_config_hash_prefix=None,
    )
    svc = _make_service(repo)
    with pytest.raises(SchemaIncompatibleException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="sm",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_idempotency_returns_cached() -> None:
    repo = _base_repository()
    tid = uuid4()
    tcid = uuid4()
    trid = uuid4()
    cid = uuid4()
    cached = {
        "id": str(trid),
        "tool_config_id": str(tcid),
        "agent_run_id": None,
        "node_run_id": str(uuid4()),
        "status": RunStatus.CREATED.value,
        "canonical_status": ToolRunStatus.CREATED.value,
        "correlation_id": str(cid),
        "started_at": None,
        "finished_at": None,
        "input": {},
        "output": {},
        "error": {},
        "idempotency_key": "ik",
        "has_side_effect": False,
        "estimated_cost": None,
        "billing_policy_version_id": str(uuid4()),
    }
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=uuid4())
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    svc.idempotency.get = AsyncMock(return_value={"response": cached})
    out = await svc.create_tool_run(
        tenant_id=tid,
        endpoint="/e",
        idempotency_key="ik",
        tool_run=ToolRunCreate(
            tool_config_id=tcid,
            node_run_id=uuid4(),
            input={},
            has_side_effect=False,
        ),
    )
    assert str(out.id) == str(trid)


@pytest.mark.asyncio
async def test_create_tool_run_flow_run_missing_after_create() -> None:
    repo = _base_repository()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=uuid4())
    repo.get_flow_run_id_for_tool_run = AsyncMock(return_value=uuid4())
    repo.get_flow_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="gff",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_flow_run_flow_snapshot_present_but_graph_snapshot_missing() -> None:
    """658–659: flow_snapshot exists but graph_snapshot never resolved (659)."""
    tid, fvid, fid, dep_id, fs_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    repo = _repo_happy_create_flow(tid, fvid, fid)
    repo.get_active_flow_deployment = AsyncMock(
        return_value=SimpleNamespace(flow_snapshot_id=fs_id, flow_deployment_id=dep_id)
    )
    repo.get_flow_snapshot_by_id = AsyncMock(
        return_value=SimpleNamespace(
            flow_snapshot_id=fs_id,
            snapshot={},
            runtime_policy={},
            tool_catalog={},
            llm_provider_config_hash=None,
            temporal_workflow_id=None,
            temporal_run_id=None,
            to_dict=lambda: {},
        )
    )
    repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with patch("domain.execution.services.execution_service.settings") as mock_settings:
        mock_settings.RUNTIME_LEGACY_GRAPH_CONTRACT_ENABLED = False
        mock_settings.TEMPORAL_ENABLED = False
        with pytest.raises(ResourceBlockedServiceException, match="flow_graph_snapshot_missing"):
            await svc.create_flow_run(
                tenant_id=tid,
                endpoint="/e",
                idempotency_key="gsmiss",
                flow_run=FlowRunCreate(
                    flow_version_id=fvid,
                    session_id=uuid4(),
                    user_id="u",
                    input=FlowRunInput(user_input="x"),
                ),
            )


@pytest.mark.asyncio
async def test_create_agent_run_rag_rejected_wrong_tenant() -> None:
    repo = _base_repository()
    tenant_id = uuid4()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    rcid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=rcid,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=rcid,
        ai_execution_policy_version_id=pol_id,
        system_prompt="x",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    svc = _make_service(repo)
    svc._rag_repository.get_rag_config = AsyncMock(
        return_value=SimpleNamespace(
            tenant_id=uuid4(),
            corpus_kind=RagCorpusKind.TENANT_KNOWLEDGE,
        )
    )
    with pytest.raises(RagNotAllowedException):
        await svc.create_agent_run(
            tenant_id=tenant_id,
            endpoint="/e",
            idempotency_key="ragt",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_agent_run_system_prompt_hash_non_empty() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="  hello  ",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    svc = _make_service(repo)
    await svc.create_agent_run(
        tenant_id=uuid4(),
        endpoint="/e",
        idempotency_key="sph",
        agent_run=AgentRunCreate(
            node_run_id=uuid4(),
            agent_version_id=av_id,
            input={},
        ),
    )
    repo.create_agent_run.assert_awaited()
    call_kw = repo.create_agent_run.await_args.kwargs
    assert call_kw.get("system_prompt_hash") is not None


@pytest.mark.asyncio
async def test_create_agent_run_idempotency_in_progress() -> None:
    repo = _base_repository()
    frid = uuid4()
    av_id = uuid4()
    pol_id = uuid4()
    mid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)
    repo.get_node.return_value = SimpleNamespace(
        node_id=uuid4(),
        node_prompt_id=uuid4(),
        allow_rag_tenant=False,
        allow_user_memory_structured=False,
        allow_user_memory_vector=False,
        rag_config_id=None,
        allow_session_context=False,
        allow_memory_write=False,
    )
    repo.get_agent_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED,
        agent_id=uuid4(),
        rag_config_id=None,
        ai_execution_policy_version_id=pol_id,
        system_prompt="",
    )
    repo.get_active_agent_version_id = AsyncMock(return_value=av_id)
    repo.get_ai_execution_policy_version.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, model_id=mid
    )
    repo.get_model.return_value = SimpleNamespace(name="m")
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    svc.idempotency.get = AsyncMock(return_value={})
    with pytest.raises(IdempotencyInProgressException):
        await svc.create_agent_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="aip",
            agent_run=AgentRunCreate(
                node_run_id=uuid4(),
                agent_version_id=av_id,
                input={},
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_node_run_id_not_found() -> None:
    repo = _base_repository()
    repo.get_node_run = AsyncMock(return_value=None)
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="node_run_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="nr",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_via_node_limit_exceeded_emits_event() -> None:
    repo = _base_repository()
    nrid = uuid4()
    frid = uuid4()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=frid)

    async def _lim(**_k):
        raise LimitExceededException(message="cap")

    svc = _make_service(repo)
    svc.limits.assert_can_create_tool_run = _lim
    repo.get_flow_run.return_value = SimpleNamespace(session_id=uuid4())
    with pytest.raises(LimitExceededException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="tle",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=nrid,
                input={},
                has_side_effect=False,
            ),
        )
    repo.append_execution_event.assert_awaited()


@pytest.mark.asyncio
async def test_create_tool_run_agent_lookup_none_after_config() -> None:
    repo = _base_repository()
    ar_id = uuid4()
    repo.get_agent_run = AsyncMock(
        side_effect=[
            SimpleNamespace(agent_version_id=uuid4(), node_run_id=uuid4()),
            None,
        ]
    )
    repo.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
    repo.get_tool_config.return_value = SimpleNamespace(
        status=VersionStatus.PUBLISHED, schema_version=None, config_hash=None
    )
    svc = _make_service(repo)
    with pytest.raises(NotFoundServiceException, match="agent_run_not_found"):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="agn",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                agent_run_id=ar_id,
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_create_tool_run_idempotency_in_progress() -> None:
    repo = _base_repository()
    repo.get_node_run.return_value = SimpleNamespace(node_id=uuid4(), flow_run_id=uuid4())
    svc = _make_service(repo)
    svc.idempotency.try_acquire = AsyncMock(return_value=False)
    svc.idempotency.get = AsyncMock(return_value={})
    with pytest.raises(IdempotencyInProgressException):
        await svc.create_tool_run(
            tenant_id=uuid4(),
            endpoint="/e",
            idempotency_key="tip",
            tool_run=ToolRunCreate(
                tool_config_id=uuid4(),
                node_run_id=uuid4(),
                input={},
                has_side_effect=False,
            ),
        )


@pytest.mark.asyncio
async def test_get_flow_run_failure_reason_invalid_enum_ignored() -> None:
    repo = _base_repository()
    frid = uuid4()
    repo.get_flow_run.return_value = _flow_run_orm_like(
        flow_run_id=frid,
        flow_version_id=uuid4(),
        status=RunStatus.FAILED.value,
        canonical_status=FlowRunStatus.FAILED.value,
    )
    ev = SimpleNamespace(
        type=ExecutionEventType.FlowFailed,
        payload={"reason": "NOT_A_REAL_REASON"},
    )
    repo.list_execution_events = AsyncMock(return_value=[ev])
    svc = _make_service(repo)
    out = await svc.get_flow_run(str(frid))
    assert out.failure_reason is None
