import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.schemas.execution import (
    AgentRunCreate,
    FlowRunCreate,
    FlowRunInput,
    FlowRunResumeInput,
    ToolRunCreate,
)
from domain.governance.schemas.runtime_policy import (
    ResolvedRuntimePolicy,
    RuntimePolicyDefinition,
    RuntimePolicyScope,
    RuntimePolicySource,
)
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan
from domain.execution.services.state_machine import (
    RunStatus,
    RunLifecycleStateMachine,
    AgentRunStatus,
    FlowRunStatus,
)
from domain.rag.schemas.rag import RagCorpusKind
from exceptions.service_exceptions import (
    AIOutputValidationException,
    IdempotencyInProgressException,
    NotFoundServiceException,
    RagNotAllowedException,
    ResourceBlockedServiceException,
    SchemaIncompatibleException,
    DomainValidationException,
)


class TestExecutionService:
    _TEST_USER_ID = "test-user"

    @staticmethod
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

    class _FakeTracer:
        def observe(self, *, as_type, name, input, metadata=None):
            return contextlib.nullcontext()

        def flow(self, *, trace=None, input=None):
            return contextlib.nullcontext()

        def start_flow_trace(self, **kwargs):
            return TraceContext(
                trace_id=kwargs["trace_id"],
                flow_run_id=kwargs["flow_run_id"],
                tenant_id=kwargs["tenant_id"],
                session_id=kwargs.get("session_id"),
                user_id=kwargs.get("user_id"),
                root_observation_id=None,
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

    @pytest.fixture
    def repository(self):
        repo = MagicMock()
        repo.db = MagicMock()
        repo.cache_adapter = MagicMock()
        graph_snap_id = uuid4()
        repo.get_flow_graph_snapshot_by_flow_version = AsyncMock(
            return_value=SimpleNamespace(
                graph_hash="test-graph-hash",
                flow_graph_snapshot_id=graph_snap_id,
                snapshot=self._minimal_graph_snapshot(),
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
        repo.get_flow_version = AsyncMock(
            return_value=SimpleNamespace(status="PUBLISHED")
        )
        repo.get_flow = AsyncMock(return_value=SimpleNamespace(tenant_id=uuid4(), name="f"))
        repo.get_active_flow_version_id = AsyncMock(return_value=uuid4())
        repo.get_tool_config = AsyncMock(
            return_value=SimpleNamespace(
                status="PUBLISHED", schema_version=None, config_hash=None
            )
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
            )
        )
        repo.get_flow_context = AsyncMock(return_value=(uuid4(), uuid4()))
        return repo

    @pytest.fixture
    def idempotency_service(self):
        from domain.execution.adapters.idempotency_service import IdempotencyService

        service = MagicMock(spec=IdempotencyService)
        service.build_key = MagicMock(return_value="test-key")
        service.try_acquire = AsyncMock(return_value=True)
        service.get = AsyncMock(return_value=None)
        service.set_result = AsyncMock()
        return service

    @pytest.fixture
    def execution_service(self, repository, idempotency_service):
        limits = MagicMock()
        limits.assert_can_create_agent_run = AsyncMock()
        limits.assert_can_create_tool_run = AsyncMock()
        service = ExecutionService(
            repository=repository,
            idempotency=idempotency_service,
            lifecycle=RunLifecycleStateMachine(),
            limits=limits,
            tracer=self._FakeTracer(),
        )
        service.llm_executor = MagicMock()
        service.runtime = MagicMock()
        service.runtime.run = AsyncMock()
        service.tools_service.list_available_tools_for_execution = AsyncMock(
            return_value=[]
        )
        service.cache_adapter.get = AsyncMock(return_value=None)
        service.cache_adapter.set = AsyncMock()
        service.hook.on_flow_start = AsyncMock()
        service._rag_repository.get_rag_config = AsyncMock(return_value=None)
        resolved = ResolvedRuntimePolicy(
            source=RuntimePolicySource.DEFAULT,
            runtime_policy_id=None,
            version="1",
            definition=RuntimePolicyDefinition.model_validate(
                service.default_policy["policy_definition"]
            ),
            scope=RuntimePolicyScope.TENANT,
            flow_id=None,
        )
        service.policy_resolver.resolve = AsyncMock(return_value=resolved)
        return service

    @pytest.mark.asyncio
    async def test_create_flow_run_creates_new_run_when_idempotency_key_not_used(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "unique-key-123"
        flow_id = uuid4()
        payload = FlowRunCreate(
            flow_version_id=uuid4(),
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
            input=FlowRunInput(user_input="data"),
        )
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            flow_id=flow_id,
            flow_version_id=payload.flow_version_id,
            to_dict=lambda: {},
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id, name="f")
        repository.get_active_flow_version_id.return_value = payload.flow_version_id

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            flow_run=payload,
        )

        assert result.status == RunStatus.CREATED
        assert result.input == payload.input.model_dump(mode="json")
        assert result.correlation_id is not None
        assert result.interaction_id is not None
        repository.create_flow_run.assert_called_once()
        repository.create_interaction.assert_called_once()
        repository.link_interaction_to_flow_run.assert_called_once()
        idempotency_service.try_acquire.assert_called_once()
        idempotency_service.set_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_run_returns_existing_when_idempotency_key_reused(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "reused-key-123"
        existing_flow_run = FlowRunCreate(
            flow_version_id=uuid4(),
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
            input=FlowRunInput(user_input="existing"),
        )

        idempotency_service.try_acquire.return_value = False
        idempotency_service.get.return_value = {
            "response": {
                "id": str(uuid4()),
                "flow_version_id": str(existing_flow_run.flow_version_id),
                "session_id": str(existing_flow_run.session_id),
                "user_id": existing_flow_run.user_id,
                "status": RunStatus.COMPLETED,
                "canonical_status": "SUCCESS",
                "correlation_id": str(uuid4()),
                "started_at": None,
                "finished_at": None,
                "input": existing_flow_run.input.model_dump(mode="json"),
                "output": {},
                "error": {},
                "origin_flow_run_id": None,
            }
        }

        flow_id = uuid4()
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            flow_id=flow_id,
            flow_version_id=existing_flow_run.flow_version_id,
            to_dict=lambda: {},
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id, name="f")
        repository.get_active_flow_version_id.return_value = (
            existing_flow_run.flow_version_id
        )

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            flow_run=existing_flow_run,
        )

        assert result.status == RunStatus.COMPLETED
        repository.create_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_flow_run_raises_when_request_in_progress(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "in-progress-key"
        payload = FlowRunCreate(
            flow_version_id=uuid4(),
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
        )

        idempotency_service.try_acquire.return_value = False
        idempotency_service.get.return_value = {"status": "PROCESSING"}

        flow_id = uuid4()
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            flow_id=flow_id,
            flow_version_id=payload.flow_version_id,
            to_dict=lambda: {},
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id, name="f")
        repository.get_active_flow_version_id.return_value = payload.flow_version_id

        with pytest.raises(IdempotencyInProgressException):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                flow_run=payload,
            )

    @pytest.mark.asyncio
    async def test_create_flow_run_supports_re_run_with_origin_reference(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "rerun-key-123"
        origin_flow_run_id = uuid4()
        flow_id = uuid4()
        payload = FlowRunCreate(
            flow_version_id=uuid4(),
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
            origin_flow_run_id=origin_flow_run_id,
            input=FlowRunInput(user_input="rerun"),
        )
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            flow_id=flow_id,
            flow_version_id=payload.flow_version_id,
            to_dict=lambda: {},
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id, name="f")
        repository.get_active_flow_version_id.return_value = payload.flow_version_id

        new_run_id = uuid4()
        repository.create_flow_run.return_value = new_run_id
        origin_correlation = uuid4()

        async def graph_state_side_effect(fid):
            if fid == origin_flow_run_id:
                return SimpleNamespace(
                    state={
                        "resume_to_node_id": "node-a",
                        "state": {},
                        "memory": [],
                    }
                )
            return None

        repository.get_graph_state = AsyncMock(side_effect=graph_state_side_effect)

        async def flow_run_side_effect(fid):
            if fid == origin_flow_run_id:
                return SimpleNamespace(
                    flow_run_id=origin_flow_run_id,
                    status=RunStatus.WAITING_INPUT,
                    canonical_status=FlowRunStatus.WAITING,
                    flow_version_id=payload.flow_version_id,
                    session_id=payload.session_id,
                    correlation_id=origin_correlation,
                    user_id=payload.user_id,
                    input={},
                    output={},
                    error={},
                    interaction_id=None,
                    started_at=None,
                    finished_at=None,
                    waiting_reason=None,
                    waiting_deadline_at=None,
                    trace_id=uuid4(),
                    root_observation_id=None,
                    flow_graph_snapshot_id=uuid4(),
                    flow_snapshot_id=None,
                    flow_deployment_id=None,
                    runtime_contract={},
                    execution_plan_hash=None,
                    runtime_policy_hash=None,
                    tool_catalog_hash=None,
                    llm_provider_config_hash=None,
                )
            if fid == new_run_id:
                return SimpleNamespace(
                    flow_run_id=new_run_id,
                    origin_flow_run_id=origin_flow_run_id,
                    flow_version_id=payload.flow_version_id,
                    session_id=payload.session_id,
                    user_id=payload.user_id,
                    interaction_id=uuid4(),
                    status=RunStatus.COMPLETED,
                    canonical_status=FlowRunStatus.COMPLETED,
                    correlation_id=uuid4(),
                    started_at=None,
                    finished_at=None,
                    waiting_reason=None,
                    waiting_deadline_at=None,
                    input=payload.input.model_dump(mode="json"),
                    output={},
                    error={},
                    trace_id=uuid4(),
                    root_observation_id=None,
                    flow_graph_snapshot_id=uuid4(),
                    flow_snapshot_id=None,
                    flow_deployment_id=None,
                    runtime_contract={},
                    execution_plan_hash=None,
                    runtime_policy_hash=None,
                    tool_catalog_hash=None,
                    llm_provider_config_hash=None,
                )
            return None

        repository.get_flow_run = AsyncMock(side_effect=flow_run_side_effect)

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            flow_run=payload,
        )

        assert result.origin_flow_run_id == origin_flow_run_id

    @pytest.mark.asyncio
    async def test_resume_flow_run_uses_graph_state_for_start_node(
        self, execution_service, repository
    ):
        flow_run_id = uuid4()
        flow_version_id = uuid4()
        flow_id = uuid4()
        session_id = uuid4()
        tenant_id = uuid4()
        correlation_id = uuid4()
        graph_snapshot_id = uuid4()
        resume_node_id = "resume-node"
        plan = ExecutionPlan(
            start_node_id=resume_node_id,
            ordered_nodes=[],
            adjacency_map={},
            terminal_nodes=set(),
            structural_hash="hash",
            nodes={},
        )

        repository.get_flow_run.return_value = SimpleNamespace(
            flow_run_id=flow_run_id,
            user_id="resume-user",
            origin_flow_run_id=None,
            flow_version_id=flow_version_id,
            session_id=session_id,
            interaction_id=None,
            status="RUNNING",
            canonical_status="RUNNING",
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            waiting_reason=None,
            waiting_deadline_at=None,
            input={"user_input": "resume"},
            output={},
            error={},
            failure_reason=None,
            trace_id=uuid4(),
            root_observation_id=None,
            flow_graph_snapshot_id=graph_snapshot_id,
            flow_snapshot_id=None,
            flow_deployment_id=None,
            runtime_contract={},
            execution_plan_hash=None,
            runtime_policy_hash=None,
            tool_catalog_hash=None,
            llm_provider_config_hash=None,
        )
        repository.get_flow_context.return_value = (session_id, tenant_id)
        repository.get_graph_state = AsyncMock(
            return_value=SimpleNamespace(
                state={
                    "resume_to_node_id": resume_node_id,
                    "state": {"key": "value"},
                    "memory": [{"memory": "entry"}],
                }
            )
        )
        repository.get_flow_version.return_value = SimpleNamespace(
            flow_id=flow_id, flow_version_id=flow_version_id
        )
        repository.get_flow_graph_snapshot_by_flow_version.return_value = SimpleNamespace(
            graph_hash="hash",
            flow_graph_snapshot_id=graph_snapshot_id,
            snapshot={"start_node": resume_node_id, "nodes": {}, "edges": []},
        )
        repository.create_interaction.return_value = uuid4()
        repository.link_interaction_to_flow_run = AsyncMock()
        repository.set_flow_run_status = AsyncMock()
        repository.set_root_observation_id = AsyncMock()

        execution_service.tools_service = MagicMock()
        execution_service.tools_service.list_available_tools_for_execution = AsyncMock(
            return_value=[]
        )
        execution_service.cache_adapter.get = AsyncMock(
            return_value=plan.model_dump(mode="json")
        )
        execution_service.cache_adapter.set = AsyncMock()
        execution_service.runtime.run = AsyncMock()

        result = await execution_service.resume_flow_run(
            flow_run_id=flow_run_id,
            input_payload=FlowRunResumeInput(user_id="resume-user", user_input="resume"),
            channel="http",
            headers={},
            external_message_id=None,
            request_id=None,
            trace_id=None,
        )

        assert result.id == flow_run_id
        execution_service.runtime.run.assert_called_once()
        _, kwargs = execution_service.runtime.run.call_args
        assert kwargs["start_node_id"] == resume_node_id
        repository.create_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_tool_run_creates_new_run_when_idempotency_key_not_used(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/tool-runs"
        idempotency_key = "tool-key-123"
        node_run_id = uuid4()
        payload = ToolRunCreate(
            tool_config_id=uuid4(),
            node_run_id=node_run_id,
            input={"tool": "input"},
            has_side_effect=True,
        )
        repository.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())

        result = await execution_service.create_tool_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            tool_run=payload,
        )

        assert result.status == RunStatus.CREATED
        assert result.input == payload.input
        assert result.has_side_effect is True
        assert result.idempotency_key == idempotency_key
        repository.create_tool_run.assert_called_once()
        idempotency_service.try_acquire.assert_called_once()
        idempotency_service.set_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_run_blocks_draft_status(self, execution_service, repository):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "blocked-flow"
        payload = FlowRunCreate(
            flow_version_id=uuid4(),
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
        )

        repository.get_flow_version.return_value = SimpleNamespace(
            status="DRAFT", flow_id=uuid4(), to_dict=lambda: {}
        )

        with pytest.raises(ResourceBlockedServiceException, match="flow_version_not_published"):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                flow_run=payload,
            )

    @pytest.mark.asyncio
    async def test_create_flow_run_blocks_when_flow_not_active(
        self, execution_service, repository
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "no-active"
        flow_id = uuid4()
        flow_version_id = uuid4()
        payload = FlowRunCreate(
            flow_version_id=flow_version_id,
            session_id=uuid4(),
            user_id=self._TEST_USER_ID,
        )

        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED", flow_id=flow_id, to_dict=lambda: {}
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id, name="f")
        repository.get_active_flow_version_id.return_value = None

        with pytest.raises(ResourceBlockedServiceException, match="flow_not_active"):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                flow_run=payload,
            )

    @pytest.mark.asyncio
    async def test_create_tool_run_blocks_draft_status(self, execution_service, repository):
        tenant_id = uuid4()
        endpoint = "/core/v1/tool-runs"
        idempotency_key = "blocked-tool"
        payload = ToolRunCreate(tool_config_id=uuid4(), node_run_id=uuid4())
        repository.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())

        repository.get_tool_config.return_value = SimpleNamespace(
            status="DRAFT", schema_version=None, config_hash=None
        )

        with pytest.raises(ResourceBlockedServiceException, match="tool_config_blocked"):
            await execution_service.create_tool_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                tool_run=payload,
            )

    @pytest.mark.asyncio
    async def test_create_tool_run_validates_schema_version(
        self, execution_service, repository
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/tool-runs"
        idempotency_key = "schema-mismatch"
        agent_run_id = uuid4()
        payload = ToolRunCreate(
            tool_config_id=uuid4(),
            agent_run_id=agent_run_id,
        )

        repository.get_tool_config.return_value = SimpleNamespace(
            status="PUBLISHED", schema_version=1, config_hash="abc"
        )
        repository.get_agent_run.return_value = SimpleNamespace(
            agent_version_id=uuid4(), node_run_id=uuid4()
        )
        repository.get_node_run.return_value = SimpleNamespace(flow_run_id=uuid4(), node_id=uuid4())
        repository.get_agent_version.return_value = SimpleNamespace(
            supported_tool_schema_version=2, supported_tool_config_hash_prefix=None
        )

        with pytest.raises(SchemaIncompatibleException, match="tool_config_schema_incompatible"):
            await execution_service.create_tool_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                tool_run=payload,
            )

    @pytest.mark.asyncio
    async def test_create_tool_run_requires_parent(self, execution_service):
        with pytest.raises(DomainValidationException, match="tool_run_missing_parent"):
            await execution_service.create_tool_run(
                tenant_id=uuid4(),
                endpoint="/core/v1/tool-runs",
                idempotency_key="k",
                tool_run=ToolRunCreate(tool_config_id=uuid4()),
            )

    @pytest.mark.asyncio
    async def test_create_agent_run_enforces_ai_task_and_policy(
        self, execution_service, repository, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/executions/agent-runs"
        idempotency_key = "agent-run-key"
        node_run_id = uuid4()
        ai_task_id = uuid4()
        node_id = uuid4()
        agent_version_id = uuid4()
        policy_version_id = uuid4()
        model_id = uuid4()

        repository.get_node_run.return_value = SimpleNamespace(
            node_id=uuid4(), flow_run_id=uuid4()
        )
        repository.get_node.return_value = SimpleNamespace(
            node_id=node_id,
            node_prompt_id=uuid4(),
            ai_task_id=ai_task_id,
            allow_rag_tenant=False,
            allow_user_memory_structured=False,
            allow_user_memory_vector=False,
            rag_config_id=None,
            allow_session_context=False,
            allow_memory_write=False,
        )
        repository.get_ai_task.return_value = SimpleNamespace(name="IntentClassifier")
        repository.get_agent_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            agent_id=uuid4(),
            rag_config_id=None,
            ai_execution_policy_version_id=policy_version_id,
            system_prompt="",
        )
        repository.get_active_agent_version_id.return_value = agent_version_id
        repository.get_ai_execution_policy_version.return_value = SimpleNamespace(
            status="PUBLISHED", model_id=model_id
        )
        repository.get_model.return_value = SimpleNamespace(name="gpt-4o")

        payload = AgentRunCreate(
            node_run_id=node_run_id,
            agent_version_id=agent_version_id,
            ai_execution_policy_version_id=policy_version_id,
            input={"prompt": "data"},
        )

        result = await execution_service.create_agent_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            agent_run=payload,
        )

        assert result.status == RunStatus.CREATED
        assert result.canonical_status == AgentRunStatus.CREATED
        assert result.runtime_snapshot["node_id"] == str(node_id)
        repository.create_agent_run.assert_called_once()
        repository.append_execution_event.assert_called_once()
        idempotency_service.set_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_run_blocks_rag_for_incompatible_task(
        self, execution_service, repository
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/executions/agent-runs"
        idempotency_key = "agent-run-rag"
        node_run_id = uuid4()
        ai_task_id = uuid4()
        agent_version_id = uuid4()
        policy_version_id = uuid4()
        model_id = uuid4()

        repository.get_node_run.return_value = SimpleNamespace(
            node_id=uuid4(), flow_run_id=uuid4()
        )
        rag_cfg = uuid4()
        repository.get_node.return_value = SimpleNamespace(
            node_id=uuid4(),
            node_prompt_id=uuid4(),
            ai_task_id=ai_task_id,
            allow_rag_tenant=False,
            allow_user_memory_structured=False,
            allow_user_memory_vector=False,
            rag_config_id=None,
            allow_session_context=False,
            allow_memory_write=False,
        )
        repository.get_ai_task.return_value = SimpleNamespace(name="ContentModeration")
        repository.get_agent_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            agent_id=uuid4(),
            rag_config_id=rag_cfg,
            ai_execution_policy_version_id=policy_version_id,
            system_prompt="",
        )
        repository.get_active_agent_version_id.return_value = agent_version_id
        repository.get_ai_execution_policy_version.return_value = SimpleNamespace(
            status="PUBLISHED", model_id=model_id
        )
        repository.get_model.return_value = SimpleNamespace(name="gpt-4o")
        execution_service._rag_repository.get_rag_config = AsyncMock(
            return_value=SimpleNamespace(
                tenant_id=tenant_id,
                corpus_kind=RagCorpusKind.TENANT_KNOWLEDGE.value,
            )
        )

        payload = AgentRunCreate(
            node_run_id=node_run_id,
            agent_version_id=agent_version_id,
            ai_execution_policy_version_id=policy_version_id,
        )

        with pytest.raises(RagNotAllowedException, match="rag_not_allowed_for_task"):
            await execution_service.create_agent_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                agent_run=payload,
            )

    @pytest.mark.asyncio
    async def test_complete_agent_run_validates_output_schema(
        self, execution_service, repository
    ):
        from pydantic import BaseModel

        agent_run_id = uuid4()
        node_run_id = uuid4()
        flow_run_id = uuid4()
        correlation_id = uuid4()

        class OutputSchema(BaseModel):
            answer: str

        repository.get_agent_run.return_value = SimpleNamespace(
            agent_run_id=agent_run_id,
            node_run_id=node_run_id,
            agent_version_id=uuid4(),
            ai_execution_policy_version_id=uuid4(),
            correlation_id=correlation_id,
            model="gpt-4o",
            ai_task_id=uuid4(),
            input={"prompt": "ok"},
            runtime_snapshot={},
            runtime_snapshot_hash=None,
        )
        repository.get_node_run.return_value = SimpleNamespace(
            node_id=uuid4(), flow_run_id=flow_run_id
        )

        with pytest.raises(AIOutputValidationException, match="ai_output_validation_failed"):
            await execution_service.complete_agent_run(
                agent_run_id=agent_run_id,
                raw_output={"not_answer": True},
                output_schema=OutputSchema,
            )

        repository.update_agent_run_result.assert_called_once()
        repository.append_execution_event.assert_called_once()

        repository.update_agent_run_result.reset_mock()
        repository.append_execution_event.reset_mock()

        result = await execution_service.complete_agent_run(
            agent_run_id=agent_run_id,
            raw_output={"answer": "ok"},
            output_schema=OutputSchema,
            metrics={"input_tokens": 10, "output_tokens": 5, "estimated_cost": 0.001},
        )

        assert result.output.get("answer") == "ok"
        repository.update_agent_run_result.assert_called_once()
        repository.append_execution_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_flow_run_returns_complete_flow_run(
        self, execution_service, repository
    ):
        from datetime import datetime, timezone

        flow_run_id = uuid4()
        session_id = uuid4()
        started_at = datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)

        repository.get_flow_run.return_value = SimpleNamespace(
            flow_run_id=flow_run_id,
            origin_flow_run_id=None,
            flow_version_id=uuid4(),
            session_id=session_id,
            user_id=self._TEST_USER_ID,
            interaction_id=uuid4(),
            status="COMPLETED",
            canonical_status="SUCCESS",
            correlation_id=uuid4(),
            started_at=started_at,
            finished_at=finished_at,
            waiting_reason=None,
            waiting_deadline_at=None,
            input={"test": "input"},
            output={"test": "output"},
            error={},
            trace_id=uuid4(),
            root_observation_id=None,
            flow_graph_snapshot_id=uuid4(),
            flow_snapshot_id=None,
            flow_deployment_id=None,
            runtime_contract={},
            execution_plan_hash="hash1",
            runtime_policy_hash="hash2",
            tool_catalog_hash="hash3",
            llm_provider_config_hash="hash4",
        )
        repository.list_execution_events = AsyncMock(return_value=[])

        result = await execution_service.get_flow_run(str(flow_run_id))

        assert result.id == flow_run_id
        assert result.status == "COMPLETED"
        assert result.trace_id is not None
        assert result.execution_plan_hash == "hash1"
        repository.get_flow_run.assert_called_once_with(flow_run_id)

    @pytest.mark.asyncio
    async def test_get_flow_run_raises_when_not_found(
        self, execution_service, repository
    ):
        flow_run_id = uuid4()
        repository.get_flow_run.return_value = None

        with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
            await execution_service.get_flow_run(str(flow_run_id))

    @pytest.mark.asyncio
    async def test_get_graph_state_returns_graph_state(
        self, execution_service, repository
    ):
        flow_run_id = uuid4()
        graph_state_id = uuid4()
        last_node_run_id = uuid4()

        repository.get_flow_run.return_value = SimpleNamespace(
            flow_run_id=flow_run_id, session_id=uuid4()
        )
        repository.get_graph_state.return_value = SimpleNamespace(
            graph_state_id=graph_state_id,
            flow_run_id=flow_run_id,
            state={"key": "value"},
            last_node_run_id=last_node_run_id,
        )

        result = await execution_service.get_graph_state(str(flow_run_id))

        assert result.id == graph_state_id
        assert result.flow_run_id == flow_run_id
        assert result.state == {"key": "value"}
        assert result.last_node_run_id == last_node_run_id
        repository.get_flow_run.assert_called_once_with(flow_run_id)
        repository.get_graph_state.assert_called_once_with(flow_run_id)

    @pytest.mark.asyncio
    async def test_get_graph_state_raises_when_flow_run_not_found(
        self, execution_service, repository
    ):
        flow_run_id = uuid4()
        repository.get_flow_run.return_value = None

        with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
            await execution_service.get_graph_state(str(flow_run_id))

    @pytest.mark.asyncio
    async def test_get_graph_state_raises_when_graph_state_not_found(
        self, execution_service, repository
    ):
        flow_run_id = uuid4()
        repository.get_flow_run.return_value = SimpleNamespace(
            flow_run_id=flow_run_id, session_id=uuid4()
        )
        repository.get_graph_state.return_value = None

        with pytest.raises(NotFoundServiceException, match="graph_state_not_found"):
            await execution_service.get_graph_state(str(flow_run_id))

    @pytest.mark.asyncio
    async def test_list_node_runs_returns_empty_list_when_no_results(
        self, execution_service, repository
    ):
        tenant_id = uuid4()
        repository.list_node_runs = AsyncMock(return_value=[])

        result = await execution_service.list_node_runs(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

        assert result == []
        repository.list_node_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_node_runs_returns_node_runs_filtered_by_tenant(
        self, execution_service, repository
    ):
        from datetime import datetime, timezone

        tenant_id = uuid4()
        flow_run_id = uuid4()
        node_run_id = uuid4()
        started_at = datetime.now(timezone.utc)

        mock_node_run = SimpleNamespace(
            node_run_id=node_run_id,
            flow_run_id=flow_run_id,
            node_id=uuid4(),
            status="COMPLETED",
            canonical_status="SUCCESS",
            correlation_id=uuid4(),
            started_at=started_at,
            finished_at=None,
            input={"test": "input"},
            output={"test": "output"},
            error={},
        )
        repository.list_node_runs = AsyncMock(return_value=[mock_node_run])

        result = await execution_service.list_node_runs(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

        assert len(result) == 1
        assert result[0].id == node_run_id
        assert result[0].status == "COMPLETED"
        repository.list_node_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_agent_runs_returns_empty_list_when_no_results(
        self, execution_service, repository
    ):
        tenant_id = uuid4()
        repository.list_agent_runs = AsyncMock(return_value=[])

        result = await execution_service.list_agent_runs(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

        assert result == []
        repository.list_agent_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_agent_runs_returns_agent_runs_filtered_by_tenant(
        self, execution_service, repository
    ):
        from datetime import datetime, timezone
        from decimal import Decimal

        tenant_id = uuid4()
        flow_run_id = uuid4()
        agent_run_id = uuid4()
        started_at = datetime.now(timezone.utc)

        mock_agent_run = SimpleNamespace(
            agent_run_id=agent_run_id,
            node_run_id=uuid4(),
            ai_task_id=uuid4(),
            agent_version_id=uuid4(),
            ai_execution_policy_version_id=uuid4(),
            billing_policy_version_id=uuid4(),
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=Decimal("0.001"),
            status="COMPLETED",
            canonical_status="SUCCESS",
            correlation_id=uuid4(),
            started_at=started_at,
            finished_at=None,
            input={"test": "input"},
            output={"test": "output"},
            error={},
            runtime_snapshot={},
            runtime_snapshot_hash=None,
        )
        repository.list_agent_runs = AsyncMock(return_value=[mock_agent_run])

        result = await execution_service.list_agent_runs(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )

        assert len(result) == 1
        assert result[0].id == agent_run_id
        assert result[0].status == "COMPLETED"
        assert result[0].estimated_cost == 0.001
        repository.list_agent_runs.assert_called_once_with(
            tenant_id=tenant_id, flow_run_id=None, limit=200
        )
