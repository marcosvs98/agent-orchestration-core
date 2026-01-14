import hashlib
import json
from uuid import UUID, uuid4
from typing import Any

from pydantic import BaseModel, ValidationError

from domain.common.schemas.versioning import VersionStatus
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.ports.service import ExecutionServicePort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import (
    AgentRun,
    AgentRunCreate,
    FlowRun,
    FlowRunCreate,
    ExecutionEvent,
    ToolRun,
    ToolRunCreate,
)
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.state_machine import (
    RunStatus,
    RunLifecycleStateMachine,
    AgentRunStatus,
    FlowRunStatus,
)
from domain.execution.services.graph_runtime.executor import RuntimeExecutor
from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.runtime_policy_resolver import RuntimePolicyResolver
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
from domain.llm.services.fake_llm_provider import FakeLLMProvider
from domain.llm.services.llm_executor import LLMExecutor
from domain.llm.services.provider_selector import LLMProviderSelector
from domain.llm.services.provider_factory import LLMProviderFactory
from domain.llm.services.cost_engine import CostEngine
from domain.llm.services.circuit_breaker import CircuitBreaker
from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.governance.repositories.llm_model_mapping_repository import LLMModelMappingRepository
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.services.execution_limit_service import ExecutionLimitService
from adapters.http.hardened_http_client import HardenedHttpClient
from adapters.secrets.env_secret_resolver import EnvSecretResolver
from adapters.cache.redis_adapter import RedisAdapter

TOOL_CATALOG_HASH_PLACEHOLDER = "tool_catalog_placeholder_v1"
from exceptions.service_exceptions import NotImplementedServiceException


class ExecutionService(ExecutionServicePort):
    def __init__(
        self,
        repository: ExecutionRepository,
        idempotency: IdempotencyService,
        lifecycle: RunLifecycleStateMachine,
        limits: ExecutionLimitService,
    ) -> None:
        self.repository = repository
        self.idempotency = idempotency
        self.lifecycle = lifecycle
        self.limits = limits
        self.llm_provider = FakeLLMProvider()
        redis_adapter = RedisAdapter(silent_mode=True)
        circuit_breaker = CircuitBreaker(redis_adapter)
        http_client = HardenedHttpClient()
        secret_resolver = EnvSecretResolver()
        provider_repo = LLMProviderRepository(repository.db)
        mapping_repo = LLMModelMappingRepository(repository.db)
        pricing_repo = LLMPricingRepository(repository.db)
        provider_selector = LLMProviderSelector(provider_repo, mapping_repo, pricing_repo)
        provider_factory = LLMProviderFactory(http_client=http_client, secret_resolver=secret_resolver)
        cost_engine = CostEngine(pricing_repo)
        guardrail_engine = GuardrailEngine(redis_adapter, cost_engine)
        self.tracer = LangfuseRuntimeTracer()
        self.llm_executor = LLMExecutor(
            self.llm_provider,
            repository,
            circuit_breaker=circuit_breaker,
            cost_engine=cost_engine,
            provider_selector=provider_selector,
            provider_factory=provider_factory.build,
            guardrail_engine=guardrail_engine,
        )
        self.runtime = RuntimeExecutor(repository, registry=NodeRegistry(self.llm_executor), tracer=self.tracer)
        self.plan_compiler = GraphCompiler()
        self.plan_cache: dict[str, Any] = {}
        from domain.governance.repositories.runtime_policy_repository import RuntimePolicyRepository

        self.default_policy = {
            "version": "1",
            "policy_definition": {
                "limits": {
                    "max_nodes": 100,
                    "max_depth": 50,
                    "max_edges_per_node": 5,
                    "max_total_duration_ms": 120000,
                    "max_node_duration_ms": 30000,
                },
                "execution": {
                    "fail_on_multiple_true_edges": True,
                    "fail_on_missing_graph": True,
                    "allow_parallel_nodes": False,
                },
                "tools": {
                    "max_retries": 2,
                    "circuit_breaker": {"failure_threshold": 5, "window_seconds": 60},
                },
                "llm": {
                    "model_alias": "fake-model",
                    "max_tokens": 2048,
                    "max_latency_ms": 10000,
                    "max_cost_usd": 1.0,
                    "retry_limit": 0,
                    "fallback_model_alias": None,
                    "max_cost_usd_per_flow_run": 5.0,
                    "max_cost_usd_per_tenant_window": 50.0,
                    "tenant_cost_window_seconds": 86400,
                    "max_llm_calls_per_flow_run": 50,
                    "max_llm_calls_per_tenant_window": 500,
                    "tenant_llm_calls_window_seconds": 3600,
                    "max_latency_ms_hard": 15000,
                    "degrade_model_alias": "text-small",
                },
            },
        }
        self.policy_resolver = RuntimePolicyResolver(RuntimePolicyRepository(repository.db), self.default_policy)

    @staticmethod
    def _hash_dict(payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def create_flow_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        payload: FlowRunCreate,
        channel: str = "http",
        headers: dict[str, str] | None = None,
        external_message_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> FlowRun:
        flow_id = payload.flow_id
        flow_version_id = payload.flow_version_id
        if flow_id is None and flow_version_id is None:
            raise DomainValidationException(message="flow_id_or_flow_version_id_required")

        if flow_version_id is not None:
            flow_version = await self.repository.get_flow_version(flow_version_id)
            if flow_version is None:
                raise NotFoundServiceException(message="flow_version_not_found")
            if flow_version.status != VersionStatus.PUBLISHED:
                raise ResourceBlockedServiceException(message="flow_version_not_published")
            flow_id = flow_version.flow_id

        if flow_id is None:
            raise DomainValidationException(message="flow_id_required")

        flow = await self.repository.get_flow(flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")

        active_flow_version_id = await self.repository.get_active_flow_version_id(flow_id)
        if active_flow_version_id is None:
            raise ResourceBlockedServiceException(message="flow_not_active")
        if flow_version_id is not None and active_flow_version_id != flow_version_id:
            raise ResourceBlockedServiceException(message="flow_version_not_active")
        selected_flow_version_id = active_flow_version_id

        key = self.idempotency.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        acquired = await self.idempotency.try_acquire(key)
        if not acquired:
            existing = await self.idempotency.get(key)
            if existing and "response" in existing:
                return FlowRun.model_validate(existing["response"])
            raise IdempotencyInProgressException()

        if trace_id is None:
            trace_uuid = uuid4()
        else:
            try:
                trace_uuid = UUID(trace_id)
            except (ValueError, TypeError) as exc:
                raise DomainValidationException(message="invalid_trace_id") from exc

        interaction_id = await self.repository.create_interaction(
            session_id=payload.session_id,
            channel=channel,
            payload={
                "flow_id": str(flow_id),
                "flow_version_id": str(selected_flow_version_id),
                "input": payload.input,
            },
            headers=headers or {},
            metadata={},
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=str(trace_uuid),
        )

        correlation_id = payload.correlation_id or uuid4()
        graph_snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(selected_flow_version_id)
        if graph_snapshot is None:
            raise ResourceBlockedServiceException(message="flow_graph_snapshot_missing")

        runtime_policy = await self.policy_resolver.resolve(tenant_id=tenant_id, flow_id=flow_id)
        runtime_policy_hash = self._hash_dict(runtime_policy.definition.model_dump())
        execution_plan_hash = graph_snapshot.graph_hash
        tool_catalog_hash = TOOL_CATALOG_HASH_PLACEHOLDER
        llm_provider_config_hash = None

        flow_run_id = await self.repository.create_flow_run(
            session_id=payload.session_id,
            flow_version_id=selected_flow_version_id,
            correlation_id=correlation_id,
            origin_flow_run_id=payload.origin_flow_run_id,
            input_payload=payload.input,
            interaction_id=interaction_id,
            flow_graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
            runtime_policy_hash=runtime_policy_hash,
            tool_catalog_hash=tool_catalog_hash,
            llm_provider_config_hash=llm_provider_config_hash,
            trace_id=trace_uuid,
            root_observation_id=None,
        )
        trace_context = self.tracer.start_flow_trace(
            flow_run_id=flow_run_id,
            flow_id=flow_id,
            flow_version_id=selected_flow_version_id,
            tenant_id=tenant_id,
            session_id=payload.session_id,
            user_id=None,
            external_request_id=request_id,
            trace_id=trace_uuid,
        )
        if trace_context.root_observation_id:
            await self.repository.set_root_observation_id(
                flow_run_id=flow_run_id, root_observation_id=trace_context.root_observation_id
            )
        await self.repository.link_interaction_to_flow_run(
            interaction_id=interaction_id, flow_run_id=flow_run_id
        )
        # canonical status: CREATED
        response = FlowRun(
            id=flow_run_id,
            origin_flow_run_id=payload.origin_flow_run_id,
            flow_version_id=selected_flow_version_id,
            session_id=payload.session_id,
            interaction_id=interaction_id,
            status=RunStatus.CREATED,
            canonical_status=FlowRunStatus.CREATED,
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            input=payload.input,
            output={},
            error={},
            trace_id=trace_uuid,
            flow_graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
            runtime_policy_hash=runtime_policy_hash,
            tool_catalog_hash=tool_catalog_hash,
            llm_provider_config_hash=llm_provider_config_hash,
        )
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=payload.session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.FlowStarted,
            payload={
                "interaction_id": str(interaction_id),
                "channel": channel,
                "trace_id": str(trace_uuid),
            },
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )

        plan = self.plan_cache.get(graph_snapshot.graph_hash)
        if plan is None:
            plan = self.plan_compiler.compile(graph_snapshot.snapshot, graph_snapshot.graph_hash)
            self.plan_cache[graph_snapshot.graph_hash] = plan

        await self.runtime.run(
            tenant_id=tenant_id,
            session_id=payload.session_id,
            flow_id=flow_id,
            flow_version_id=selected_flow_version_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            trace_id=trace_uuid,
            plan=plan,
            runtime_policy=runtime_policy,
            trace_context=trace_context,
        )
        self.tracer.flush()
        await self.idempotency.set_result(
            key,
            {"flow_run_id": str(flow_run_id), "response": response.model_dump()},
        )
        return response

    async def create_agent_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        payload: AgentRunCreate,
    ) -> AgentRun:
        node_run = await self.repository.get_node_run(payload.node_run_id)
        if node_run is None:
            raise NotFoundServiceException(message="node_run_not_found")
        try:
            await self.limits.assert_can_create_agent_run(
                tenant_id=tenant_id, flow_run_id=node_run.flow_run_id
            )
        except LimitExceededException as exc:
            flow_run = await self.repository.get_flow_run(node_run.flow_run_id)
            if flow_run is None:
                raise
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=flow_run.session_id,
                flow_run_id=node_run.flow_run_id,
                event_type=ExecutionEventType.LimitExceeded,
                payload={"action": "agent_run:create", "message": exc.message},
                correlation_id=payload.correlation_id or uuid4(),
                causation_id=None,
                schema_version=1,
            )
            raise
        node = await self.repository.get_node(node_run.node_id)
        if node is None or node.ai_task_id is None:
            raise DomainValidationException(message="ai_task_missing")

        ai_task = await self.repository.get_ai_task(node.ai_task_id)
        if ai_task is None:
            raise NotFoundServiceException(message="ai_task_not_found")

        agent_version = await self.repository.get_agent_version(payload.agent_version_id)
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        if agent_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="agent_version_blocked")
        active_agent_version_id = await self.repository.get_active_agent_version_id(
            agent_version.agent_id
        )
        if active_agent_version_id is None or active_agent_version_id != payload.agent_version_id:
            raise ResourceBlockedServiceException(message="agent_version_not_active")

        policy_version = await self.repository.get_ai_execution_policy_version(
            payload.ai_execution_policy_version_id
        )
        if policy_version is None:
            raise NotFoundServiceException(message="ai_execution_policy_version_not_found")
        if policy_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="ai_execution_policy_blocked")
        if agent_version.ai_execution_policy_version_id and (
            agent_version.ai_execution_policy_version_id != payload.ai_execution_policy_version_id
        ):
            raise DomainConflictException(message="ai_execution_policy_mismatch")

        model_record = await self.repository.get_model(policy_version.model_id)
        model_name = model_record.name if model_record else None

        allowed_rag_tasks = {"IntentDetection", "SlotFilling", "ResponseFormatting"}
        blocked_rag_tasks = {"ContentModeration", "FlowDecision", "ExecutionControl"}
        if agent_version.rag_config_id:
            if ai_task.name in blocked_rag_tasks or ai_task.name not in allowed_rag_tasks:
                raise RagNotAllowedException(message="rag_not_allowed_for_task")

        billing_policy_version_id = await self.repository.get_active_billing_policy_version_id(tenant_id)
        if billing_policy_version_id is None:
            raise ResourceBlockedServiceException(message="billing_policy_not_active")

        key = self.idempotency.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        acquired = await self.idempotency.try_acquire(key)
        if not acquired:
            existing = await self.idempotency.get(key)
            if existing and "response" in existing:
                return AgentRun.model_validate(existing["response"])
            raise IdempotencyInProgressException()

        correlation_id = payload.correlation_id or uuid4()
        agent_run_id = await self.repository.create_agent_run(
            ai_task_id=node.ai_task_id,
            node_run_id=payload.node_run_id,
            agent_version_id=payload.agent_version_id,
            ai_execution_policy_version_id=payload.ai_execution_policy_version_id,
            correlation_id=correlation_id,
            input_payload=payload.input,
            model=model_name,
            billing_policy_version_id=billing_policy_version_id,
        )
        flow_run = await self.repository.get_flow_run(node_run.flow_run_id)
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=flow_run.session_id,
            flow_run_id=node_run.flow_run_id,
            event_type=ExecutionEventType.AgentRunStarted,
            payload={
                "agent_run_id": str(agent_run_id),
                "node_run_id": str(payload.node_run_id),
                "ai_task_id": str(node.ai_task_id),
                "agent_version_id": str(payload.agent_version_id),
                "policy_version_id": str(payload.ai_execution_policy_version_id),
                "billing_policy_version_id": str(billing_policy_version_id),
                "model": model_name,
            },
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )

        response = AgentRun(
            id=agent_run_id,
            node_run_id=payload.node_run_id,
            ai_task_id=node.ai_task_id,
            agent_version_id=payload.agent_version_id,
            ai_execution_policy_version_id=payload.ai_execution_policy_version_id,
            billing_policy_version_id=billing_policy_version_id,
            model=model_name,
            input_tokens=None,
            output_tokens=None,
            estimated_cost=None,
            status=RunStatus.CREATED,
            canonical_status=AgentRunStatus.CREATED,
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            input=payload.input,
            output={},
            error={},
        )
        await self.idempotency.set_result(
            key,
            {"agent_run_id": str(agent_run_id), "response": response.model_dump()},
        )
        return response

    async def complete_agent_run(
        self,
        *,
        agent_run_id: UUID,
        raw_output: dict,
        output_schema: type | None = None,
        metrics: dict | None = None,
    ) -> AgentRun:
        existing_agent_run = await self.repository.get_agent_run(agent_run_id)
        if existing_agent_run is None:
            raise NotFoundServiceException(message="agent_run_not_found")
        node_run = await self.repository.get_node_run(existing_agent_run.node_run_id)
        flow_run_id = node_run.flow_run_id if node_run else raw_output.get("flow_run_id")
        normalized_output = raw_output
        try:
            if output_schema and isinstance(output_schema, type) and issubclass(output_schema, BaseModel):
                normalized_output = output_schema.model_validate(raw_output).model_dump()
        except ValidationError as exc:
            if node_run is None:
                raise DomainValidationException(message="node_run_not_found")
            session_id, tenant_id = await self.repository.get_flow_context(node_run.flow_run_id)
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=node_run.flow_run_id,
                event_type=ExecutionEventType.AgentRunFailed,
                payload={
                    "agent_run_id": str(agent_run_id),
                    "policy_version_id": str(existing_agent_run.ai_execution_policy_version_id),
                    "tokens_input": None,
                    "tokens_output": None,
                    "cost_estimated": None,
                    "error_class": "validation",
                    "errors": exc.errors(),
                },
                correlation_id=existing_agent_run.correlation_id,
                causation_id=None,
                schema_version=1,
            )
            await self.repository.update_agent_run_result(
                agent_run_id=agent_run_id,
            status=RunStatus.FAILED,
                canonical_status=AgentRunStatus.FAILED,
                output={},
                error={"validation_errors": exc.errors()},
                input_tokens=None,
                output_tokens=None,
                estimated_cost=None,
            )
            raise AIOutputValidationException(message="ai_output_validation_failed", detail=exc.errors()) from exc

        input_tokens = None
        output_tokens = None
        estimated_cost = None
        if metrics:
            input_tokens = metrics.get("input_tokens")
            output_tokens = metrics.get("output_tokens")
            estimated_cost = metrics.get("estimated_cost")

        await self.repository.update_agent_run_result(
            agent_run_id=agent_run_id,
            status=RunStatus.COMPLETED,
            canonical_status=AgentRunStatus.COMPLETED,
            output=normalized_output,
            error={},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )
        if node_run is None:
            raise DomainValidationException(message="node_run_not_found")
        session_id, tenant_id = await self.repository.get_flow_context(node_run.flow_run_id)
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=node_run.flow_run_id,
            event_type=ExecutionEventType.AgentRunCompleted,
            payload={
                "agent_run_id": str(agent_run_id),
                "agent_version_id": str(existing_agent_run.agent_version_id),
                "policy_version_id": str(existing_agent_run.ai_execution_policy_version_id),
                "ai_task_id": str(existing_agent_run.ai_task_id) if existing_agent_run.ai_task_id else None,
                "model": existing_agent_run.model,
                "tokens_input": input_tokens,
                "tokens_output": output_tokens,
                "cost_estimated": estimated_cost,
            },
            correlation_id=existing_agent_run.correlation_id,
            causation_id=None,
            schema_version=1,
        )

        return AgentRun(
            id=agent_run_id,
            node_run_id=existing_agent_run.node_run_id,
            ai_task_id=existing_agent_run.ai_task_id,
            agent_version_id=existing_agent_run.agent_version_id,
            ai_execution_policy_version_id=existing_agent_run.ai_execution_policy_version_id,
            model=existing_agent_run.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            status=RunStatus.COMPLETED,
            canonical_status=AgentRunStatus.COMPLETED,
            correlation_id=existing_agent_run.correlation_id,
            started_at=raw_output.get("started_at"),
            finished_at=None,
            input=existing_agent_run.input or {},
            output=normalized_output,
            error={},
        )

    async def create_tool_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        payload: ToolRunCreate,
    ) -> ToolRun:
        if payload.node_run_id is None and payload.agent_run_id is None:
            raise DomainValidationException(message="tool_run_missing_parent")

        billing_policy_version_id = await self.repository.get_active_billing_policy_version_id(tenant_id)
        if billing_policy_version_id is None:
            raise ResourceBlockedServiceException(message="billing_policy_not_active")

        if payload.node_run_id:
            node_run = await self.repository.get_node_run(payload.node_run_id)
            if node_run is None:
                raise NotFoundServiceException(message="node_run_not_found")
            try:
                await self.limits.assert_can_create_tool_run(
                    tenant_id=tenant_id, flow_run_id=node_run.flow_run_id
                )
            except LimitExceededException as exc:
                flow_run = await self.repository.get_flow_run(node_run.flow_run_id)
                if flow_run is None:
                    raise
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=flow_run.session_id,
                    flow_run_id=node_run.flow_run_id,
                    event_type=ExecutionEventType.LimitExceeded,
                    payload={"action": "tool_run:create", "message": exc.message},
                    correlation_id=payload.correlation_id or uuid4(),
                    causation_id=None,
                    schema_version=1,
                )
                raise
        else:
            agent_run_id = payload.agent_run_id
            if agent_run_id is None:
                raise DomainValidationException(message="tool_run_missing_parent")
            agent_run = await self.repository.get_agent_run(agent_run_id)
            if agent_run is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            node_run = await self.repository.get_node_run(agent_run.node_run_id)
            if node_run is None:
                raise NotFoundServiceException(message="node_run_not_found")
            try:
                await self.limits.assert_can_create_tool_run(
                    tenant_id=tenant_id, flow_run_id=node_run.flow_run_id
                )
            except LimitExceededException as exc:
                flow_run = await self.repository.get_flow_run(node_run.flow_run_id)
                if flow_run is None:
                    raise
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=flow_run.session_id,
                    flow_run_id=node_run.flow_run_id,
                    event_type=ExecutionEventType.LimitExceeded,
                    payload={"action": "tool_run:create", "message": exc.message},
                    correlation_id=payload.correlation_id or uuid4(),
                    causation_id=None,
                    schema_version=1,
                )
                raise

        tool_config = await self.repository.get_tool_config(payload.tool_config_id)
        if tool_config is None:
            raise NotFoundServiceException(message="tool_config_not_found")
        if tool_config.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="tool_config_blocked")

        if payload.agent_run_id:
            agent_run = await self.repository.get_agent_run(payload.agent_run_id)
            if agent_run is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            agent_version = await self.repository.get_agent_version(agent_run.agent_version_id)
            if agent_version is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            if (
                agent_version.supported_tool_schema_version is not None
                and tool_config.schema_version is not None
                and agent_version.supported_tool_schema_version != tool_config.schema_version
            ):
                raise SchemaIncompatibleException(message="tool_config_schema_incompatible")
            if (
                agent_version.supported_tool_config_hash_prefix
                and tool_config.config_hash
                and not tool_config.config_hash.startswith(agent_version.supported_tool_config_hash_prefix)
            ):
                raise HashIncompatibleException(message="tool_config_hash_incompatible")

        key = self.idempotency.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        acquired = await self.idempotency.try_acquire(key)
        if not acquired:
            existing = await self.idempotency.get(key)
            if existing and "response" in existing:
                return ToolRun.model_validate(existing["response"])
            raise IdempotencyInProgressException()

        correlation_id = payload.correlation_id or uuid4()
        tool_run_id = await self.repository.create_tool_run(
            tool_config_id=payload.tool_config_id,
            correlation_id=correlation_id,
            agent_run_id=payload.agent_run_id,
            node_run_id=payload.node_run_id,
            idempotency_key=idempotency_key,
            has_side_effect=payload.has_side_effect,
            input_payload=payload.input,
            estimated_cost=None,
            billing_policy_version_id=billing_policy_version_id,
        )
        response = ToolRun(
            id=tool_run_id,
            tool_config_id=payload.tool_config_id,
            agent_run_id=payload.agent_run_id,
            node_run_id=payload.node_run_id,
            status=RunStatus.CREATED,
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            input=payload.input,
            output={},
            error={},
            idempotency_key=idempotency_key,
            has_side_effect=payload.has_side_effect,
            estimated_cost=None,
            billing_policy_version_id=billing_policy_version_id,
        )
        flow_run_id = await self.repository.get_flow_run_id_for_tool_run(tool_run_id)
        flow_run = await self.repository.get_flow_run(flow_run_id)
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        session_id = flow_run.session_id
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.ToolInvocationRequested,
            payload={
                "tool_run_id": str(tool_run_id),
                "tool_config_id": str(payload.tool_config_id),
                "executor_type": "http",
            },
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )
        await self.idempotency.set_result(
            key,
            {"tool_run_id": str(tool_run_id), "response": response.model_dump()},
        )
        return response

    async def get_flow_run(self, flow_run_id: str):
        # Placeholder observability endpoint
        result = await self.repository.get_flow_run(UUID(flow_run_id))
        if result is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        return FlowRun.model_validate(
            {
                "id": result.flow_run_id,
                "origin_flow_run_id": result.origin_flow_run_id,
                "flow_version_id": result.flow_version_id,
                "session_id": result.session_id,
                "interaction_id": result.interaction_id,
                "status": result.status,
                "canonical_status": result.canonical_status,
                "correlation_id": result.correlation_id,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "input": result.input,
                "output": result.output,
                "error": result.error,
            }
        )

    async def get_graph_state(self, flow_run_id: str):
        raise NotImplementedServiceException()

    async def list_node_runs(self):
        raise NotImplementedServiceException()

    async def list_agent_runs(self):
        raise NotImplementedServiceException()

    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
    ) -> list[ExecutionEvent]:
        events = await self.repository.list_execution_events(
            flow_run_id=flow_run_id, correlation_id=correlation_id, limit=limit
        )
        return [
            ExecutionEvent(
                id=e.execution_event_id,
                tenant_id=e.tenant_id,
                session_id=e.session_id,
                flow_run_id=e.flow_run_id,
                type=e.type,
                occurred_at=e.occurred_at.isoformat(),
                event_sequence=int(e.event_sequence),
                correlation_id=e.correlation_id,
                causation_id=e.causation_id,
                schema_version=int(e.schema_version),
                payload=e.payload,
            )
            for e in events
        ]
