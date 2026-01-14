from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import AgentRunCreate, FlowRunCreate, ToolRunCreate
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import (
    RunStatus,
    RunLifecycleStateMachine,
    AgentRunStatus,
)
from exceptions.service_exceptions import (
    AIOutputValidationException,
    IdempotencyInProgressException,
    RagNotAllowedException,
    ResourceBlockedServiceException,
    SchemaIncompatibleException,
    DomainValidationException,
)


class TestExecutionService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=ExecutionRepository)
        repo.create_flow_run = AsyncMock(return_value=uuid4())
        repo.create_tool_run = AsyncMock(return_value=uuid4())
        repo.create_agent_run = AsyncMock(return_value=uuid4())
        repo.update_agent_run_result = AsyncMock()
        repo.create_interaction = AsyncMock(return_value=uuid4())
        repo.link_interaction_to_flow_run = AsyncMock()
        repo.get_flow_version = AsyncMock(
            return_value=SimpleNamespace(status="PUBLISHED")
        )
        repo.get_flow = AsyncMock(return_value=SimpleNamespace(tenant_id=uuid4()))
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
        repo.get_flow_run = AsyncMock(return_value=SimpleNamespace(session_id=uuid4()))
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
        return ExecutionService(
            repository=repository,
            idempotency=idempotency_service,
            lifecycle=RunLifecycleStateMachine(),
            limits=limits,
        )

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
            input={"test": "data"},
        )
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED", flow_id=flow_id
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
        repository.get_active_flow_version_id.return_value = payload.flow_version_id

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            payload=payload,
        )

        assert result.status == RunStatus.CREATED
        assert result.input == payload.input
        assert result.correlation_id is not None
        assert result.interaction_id is not None
        repository.create_flow_run.assert_called_once()
        repository.create_interaction.assert_called_once()
        repository.link_interaction_to_flow_run.assert_called_once()
        repository.append_execution_event.assert_called_once()
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
            input={"existing": "data"},
        )

        idempotency_service.try_acquire.return_value = False
        idempotency_service.get.return_value = {
            "response": {
                "id": str(uuid4()),
                "flow_version_id": str(existing_flow_run.flow_version_id),
                "session_id": str(existing_flow_run.session_id),
                "status": RunStatus.COMPLETED,
                "correlation_id": str(uuid4()),
                "started_at": None,
                "finished_at": None,
                "input": existing_flow_run.input,
                "output": {},
                "error": {},
                "origin_flow_run_id": None,
            }
        }

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            payload=existing_flow_run,
        )

        assert result.status == RunStatus.COMPLETED
        repository.create_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_flow_run_raises_when_request_in_progress(
        self, execution_service, idempotency_service
    ):
        tenant_id = uuid4()
        endpoint = "/core/v1/flow-runs"
        idempotency_key = "in-progress-key"
        payload = FlowRunCreate(flow_version_id=uuid4(), session_id=uuid4())

        idempotency_service.try_acquire.return_value = False
        idempotency_service.get.return_value = {"status": "PROCESSING"}

        with pytest.raises(IdempotencyInProgressException):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                payload=payload,
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
            origin_flow_run_id=origin_flow_run_id,
            input={"rerun": "data"},
        )
        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED", flow_id=flow_id
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
        repository.get_active_flow_version_id.return_value = payload.flow_version_id

        result = await execution_service.create_flow_run(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            payload=payload,
        )

        assert result.origin_flow_run_id == origin_flow_run_id
        repository.create_flow_run.assert_called_once()
        call_args = repository.create_flow_run.call_args
        assert call_args.kwargs["origin_flow_run_id"] == origin_flow_run_id

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
            payload=payload,
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
        payload = FlowRunCreate(flow_version_id=uuid4(), session_id=uuid4())

        repository.get_flow_version.return_value = SimpleNamespace(status="DRAFT", flow_id=uuid4())

        with pytest.raises(ResourceBlockedServiceException, match="flow_version_not_published"):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                payload=payload,
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
        payload = FlowRunCreate(flow_version_id=flow_version_id, session_id=uuid4())

        repository.get_flow_version.return_value = SimpleNamespace(
            status="PUBLISHED", flow_id=flow_id
        )
        repository.get_flow.return_value = SimpleNamespace(tenant_id=tenant_id)
        repository.get_active_flow_version_id.return_value = None

        with pytest.raises(ResourceBlockedServiceException, match="flow_not_active"):
            await execution_service.create_flow_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                payload=payload,
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
                payload=payload,
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
                payload=payload,
            )

    @pytest.mark.asyncio
    async def test_create_tool_run_requires_parent(self, execution_service):
        with pytest.raises(DomainValidationException, match="tool_run_missing_parent"):
            await execution_service.create_tool_run(
                tenant_id=uuid4(),
                endpoint="/core/v1/tool-runs",
                idempotency_key="k",
                payload=ToolRunCreate(tool_config_id=uuid4()),
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
        agent_version_id = uuid4()
        policy_version_id = uuid4()
        model_id = uuid4()

        repository.get_node_run.return_value = SimpleNamespace(
            node_id=uuid4(), flow_run_id=uuid4()
        )
        repository.get_node.return_value = SimpleNamespace(ai_task_id=ai_task_id)
        repository.get_ai_task.return_value = SimpleNamespace(name="IntentDetection")
        repository.get_agent_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            agent_id=uuid4(),
            rag_config_id=None,
            ai_execution_policy_version_id=None,
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
            payload=payload,
        )

        assert result.status == RunStatus.CREATED
        assert result.canonical_status == AgentRunStatus.CREATED
        assert result.ai_task_id == ai_task_id
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
        repository.get_node.return_value = SimpleNamespace(ai_task_id=ai_task_id)
        repository.get_ai_task.return_value = SimpleNamespace(name="ContentModeration")
        repository.get_agent_version.return_value = SimpleNamespace(
            status="PUBLISHED",
            agent_id=uuid4(),
            rag_config_id=uuid4(),
            ai_execution_policy_version_id=None,
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
        )

        with pytest.raises(RagNotAllowedException, match="rag_not_allowed_for_task"):
            await execution_service.create_agent_run(
                tenant_id=tenant_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                payload=payload,
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
