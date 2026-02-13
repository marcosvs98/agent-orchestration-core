import hashlib
import json
from uuid import UUID, uuid4
from typing import Any

import settings

from domain.execution.services.graph_runtime.execution_plan import ExecutionPlan
from domain.execution.schemas.trace import TraceContext
from pydantic import BaseModel, ValidationError, Field, ConfigDict
from infra.database.models.conversation.session import Session as SessionModel
from domain.common.schemas.versioning import VersionStatus
from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.execution.ports.service import ExecutionServicePort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import (
    AgentRun,
    AgentRunCreate,
    Channel,
    FlowRun,
    FlowRunCreate,
    FlowRunInput,
    FlowRunResumeInput,
    ExecutionEvent,
    FlowFailureReason,
    GraphState,
    NodeRun,
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
from domain.tools.schemas.tools import AvailableTool
from domain.execution.services.graph_runtime.graph_compiler import GraphCompiler
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.observability.hooks import (
    DbExecutionEventHook,
    MemoryExtractionHook,
)
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
from domain.llm.services.llm_executor import LLMExecutor
from domain.llm.services.provider_selector import LLMProviderSelector
from domain.llm.services.provider_factory import LLMProviderFactory
from domain.llm.services.cost_engine import CostEngine
from domain.llm.services.circuit_breaker import CircuitBreaker
from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.governance.repositories.llm_model_mapping_repository import (
    LLMModelMappingRepository,
)
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.services.execution_limit_service import ExecutionLimitService
from adapters.http.hardened_http_client import HardenedHttpClient
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from adapters.secrets.env_secret_resolver import EnvSecretResolver
from adapters.cache.redis_adapter import RedisAdapter
from adapters.jobs.arq_embedding_queue import ArqEmbeddingQueueAdapter
from domain.prompts.services.prompt_service import PromptService
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from application.prompts.prompt_resolver import PromptResolver
from application.prompts.system_prompt_compiler import SystemPromptCompiler
from domain.llm.services.context_builder import ContextBuilder
from domain.context.services.retrievers import (
    TenantKnowledgeRetriever,
    UserMemoryReader,
)
from domain.context.services.rag_activation_service import RagActivationService
from domain.context.services.memory_extraction_processor import MemoryExtractionProcessor
from domain.context.services.memory_retrieval import MemoryRetrievalService
from domain.context.services.session_context import SessionContextService
from domain.context.services.memory_writer import MemoryWriteService
from domain.context.services.runtime_policy import RuntimeContextLayerPolicy
from domain.governance.services.memory_policy_service import MemoryPolicyService
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.tools.ports.service import ToolsServicePort
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.services.tools_service import ToolsService
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from infra.http_tool_executor import HttpToolExecutor


class _GraphStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    current_node_id: str | None = None
    resume_to_node_id: str | None = None
    state: dict[str, object] = Field(default_factory=dict)
    memory: list[dict[str, object]] = Field(default_factory=list)


class ExecutionService(ExecutionServicePort):
    def __init__(
        self,
        repository: ExecutionRepository,
        idempotency: IdempotencyService,
        lifecycle: RunLifecycleStateMachine,
        limits: ExecutionLimitService,
        tracer: RuntimeTracerPort,
        tools_service: ToolsServicePort | None = None,
    ) -> None:
        self.repository = repository
        self.idempotency = idempotency
        self.lifecycle = lifecycle
        self.limits = limits
        self.cache_adapter = RedisAdapter(silent_mode=True)
        circuit_breaker = CircuitBreaker(self.cache_adapter, tracer=tracer)
        http_client = HardenedHttpClient()
        secret_resolver = EnvSecretResolver()
        provider_repo = LLMProviderRepository(repository.db, tracer=tracer)
        mapping_repo = LLMModelMappingRepository(repository.db, tracer=tracer)
        pricing_repo = LLMPricingRepository(repository.db, tracer=tracer)
        provider_selector = LLMProviderSelector(
            provider_repo, mapping_repo, pricing_repo, tracer=tracer
        )
        provider_factory = LLMProviderFactory(
            http_client=http_client,
            secret_resolver=secret_resolver,
            cache_adapter=self.cache_adapter,
            tracer=tracer,
        )
        cost_engine = CostEngine(pricing_repo, tracer=tracer)
        guardrail_engine = GuardrailEngine(tracer, self.cache_adapter, cost_engine)
        self.tracer = tracer or LangfuseRuntimeTracer()
        prompt_repository = PromptRepository(repository.db, tracer=tracer)
        prompt_service = PromptService(
            repository=prompt_repository, execution_repository=repository, tracer=tracer
        )
        agents_repository = AgentsRepository(
            repository.db,
            tracer=tracer,
            cache_adapter=getattr(repository, "cache_adapter", None),
        )
        self.tools_repository = ToolsRepository(repository.db, tracer=tracer)
        if tools_service:
            self.tools_service = tools_service
        else:
            authoring_events = AuthoringEventRepository(
                repository.db, tracer=self.tracer
            )
            self.tools_service = ToolsService(
                repository=self.tools_repository,
                agents_repository=agents_repository,
                authoring_events=authoring_events,
                tracer=tracer,
            )
        self.llm_executor = LLMExecutor(
            repository,
            None,
            circuit_breaker=circuit_breaker,
            cost_engine=cost_engine,
            provider_selector=provider_selector,
            provider_factory=provider_factory.build,
            guardrail_engine=guardrail_engine,
            tracer=self.tracer,
        )
        rag_repository = RagRepository(repository.db, tracer=tracer)
        cache_adapter = RedisAdapter(silent_mode=settings.CACHE_SILENT_MODE)
        embedding_adapter = OpenAIEmbeddingAdapter(
            api_key=settings.OPENAI_API_KEY,
            model="text-embedding-3-small",
            dimension=1536,
            tracer=tracer,
            cache_adapter=cache_adapter,
        )
        rag_runtime_service = RagRuntimeService(
            repository=rag_repository,
            embedding_adapter=embedding_adapter,
            tracer=tracer,
        )
        tenant_knowledge_retriever = TenantKnowledgeRetriever(
            rag_runtime_service=rag_runtime_service,
        )
        memory_policy_service = MemoryPolicyService(repository=repository)
        rag_policy_service = RagPolicyService(repository=repository)
        rag_activation_service = RagActivationService(
            repository=repository,
            rag_repository=rag_repository,
            tools_repository=self.tools_repository,
            rag_policy_service=rag_policy_service,
            tracer=self.tracer,
        )
        user_memory_reader = UserMemoryReader(
            repository=repository,
            rag_runtime_service=rag_runtime_service,
            memory_policy_service=memory_policy_service,
            rag_activation_service=rag_activation_service,
        )
        session_context_service = SessionContextService(repository=repository)
        memory_retrieval_service = MemoryRetrievalService(
            tenant_knowledge_retriever=tenant_knowledge_retriever,
            user_memory_reader=user_memory_reader,
            session_context_service=session_context_service,
            tracer=self.tracer,
        )
        memory_write_service = MemoryWriteService(
            policy_service=memory_policy_service,
            rag_runtime_service=rag_runtime_service,
            repository=repository,
            tracer=self.tracer,
            embedding_job_queue=ArqEmbeddingQueueAdapter(),
        )
        runtime_context_policy = RuntimeContextLayerPolicy()
        context_builder = ContextBuilder(
            agents_repository,
            self.tools_repository,
            rag_runtime_service=rag_runtime_service,
            tenant_knowledge_retriever=tenant_knowledge_retriever,
            user_memory_reader=user_memory_reader,
            memory_retrieval_service=memory_retrieval_service,
            rag_activation_service=rag_activation_service,
            runtime_context_policy=runtime_context_policy,
            tracer=tracer,
        )
        system_prompt_compiler = SystemPromptCompiler(tracer)
        prompt_resolver = PromptResolver(
            prompt_service=prompt_service,
            context_builder=context_builder,
            execution_repository=repository,
            tracer=tracer,
        )
        self.prompt_repository = prompt_repository
        self.system_prompt_compiler = system_prompt_compiler
        base_hook = DbExecutionEventHook(repository, tracer=self.tracer)
        memory_extraction_processor = MemoryExtractionProcessor(
            llm_executor=self.llm_executor,
            memory_write_service=memory_write_service,
            tracer=self.tracer,
        )
        self.hook = MemoryExtractionHook(
            base_hook=base_hook,
            memory_extraction_processor=memory_extraction_processor,
            tracer=self.tracer,
        )
        tool_executor = HttpToolExecutor(tracer=tracer)
        tool_orchestrator = ToolOrchestrator(
            repository=repository,
            executor=tool_executor,
            secret_resolver=secret_resolver,
            tracer=self.tracer,
            tools_repository=self.tools_repository,
        )
        self.runtime = RuntimeExecutor(
            repository,
            registry=NodeRegistry(
                llm_executor=self.llm_executor,
                prompt_resolver=prompt_resolver,
                tool_orchestrator=tool_orchestrator,
                execution_repository=repository,
                tracer=tracer,
            ),
            tracer=self.tracer,
            hook=self.hook,
            memory_write_service=memory_write_service,
        )
        self.plan_compiler = GraphCompiler(tracer)
        from domain.governance.repositories.runtime_policy_repository import (
            RuntimePolicyRepository,
        )

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
                "memory_extraction": {},
                "memory_retrieval": {},
                "user_context_enrichment": {},
            },
        }
        self.policy_resolver = RuntimePolicyResolver(
            RuntimePolicyRepository(repository.db, tracer=tracer),
            self.default_policy,
            tracer=tracer,
        )

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
        flow_run: FlowRunCreate,
        channel: Channel = Channel.HTTP,
        headers: dict[str, str] | None = None,
        external_message_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> FlowRun:
        with self.tracer.observe(
            as_type="agent",
            name="domain.execution.execution_service.select_flow_version_and_path",
            input={
                "flow_id": str(flow_run.flow_id) if flow_run.flow_id else None,
                "flow_version_id": str(flow_run.flow_version_id)
                if flow_run.flow_version_id
                else None,
            },
        ) as agent_handle:
            flow_id = flow_run.flow_id
            flow_version_id = flow_run.flow_version_id
            if flow_id is None and flow_version_id is None:
                raise DomainValidationException(
                    message="flow_id_or_flow_version_id_required"
                )

            if flow_version_id is not None:
                flow_version = await self.repository.get_flow_version(flow_version_id)
                if flow_version is None:
                    raise NotFoundServiceException(message="flow_version_not_found")
                if flow_version.status != VersionStatus.PUBLISHED:
                    raise ResourceBlockedServiceException(
                        message="flow_version_not_published"
                    )
                flow_id = flow_version.flow_id

                if agent_handle:
                    agent_handle.success(
                        output={"flow_version": flow_version.to_dict()}
                    )

        if flow_id is None:
            raise DomainValidationException(message="flow_id_required")
        if not flow_run.user_id.strip():
            raise DomainValidationException(message="user_id_required")

        flow = await self.repository.get_flow(flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")

        active_flow_version_id = await self.repository.get_active_flow_version_id(
            flow_id
        )
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

        existing_session: SessionModel = await self.repository.get_session(
            flow_run.session_id
        )
        if existing_session is None:
            await self.repository.create_session(
                session_id=flow_run.session_id,
                tenant_id=tenant_id,
                user_id=flow_run.user_id,
            )
        elif (
            existing_session.tenant_id != tenant_id
            or existing_session.user_id != flow_run.user_id
        ):
            raise DomainConflictException(message="session_user_mismatch")

        interaction_id: UUID = await self.repository.create_interaction(
            session_id=flow_run.session_id,
            channel=channel,
            payload=flow_run.model_dump(mode="json"),
            headers=headers or {},
            metadata=flow_run.metadata,
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=str(trace_uuid),
        )

        correlation_id = flow_run.correlation_id or uuid4()
        origin_flow_run_id = flow_run.origin_flow_run_id
        origin_start_node_id: str | None = None
        origin_initial_state: dict[str, object] | None = None
        origin_initial_memory: list[dict[str, object]] | None = None
        candidates: list[UUID] = []
        if origin_flow_run_id is None and flow_run.correlation_id is not None:
            (
                origin_flow_run_id,
                candidates,
            ) = await self.repository.get_latest_waiting_flow_run_id(
                session_id=flow_run.session_id,
                correlation_id=correlation_id,
                flow_version_id=selected_flow_version_id,
                user_id=flow_run.user_id,
            )
        if len(candidates) > 1:
            with self.tracer.observe(
                as_type="event",
                name="domain.execution.execution_service.ambiguous_waiting_origin",
                input={
                    "session_id": str(flow_run.session_id),
                    "correlation_id": str(correlation_id),
                    "flow_version_id": str(selected_flow_version_id),
                    "candidate_ids": [str(candidate) for candidate in candidates],
                },
            ):
                pass
        if origin_flow_run_id is not None:
            await self.repository.acquire_flow_run_lock(
                origin_flow_run_id, owner=None, correlation_id=correlation_id
            )
            origin_flow_run = await self.repository.get_flow_run(origin_flow_run_id)
            if origin_flow_run is not None and (
                origin_flow_run.status == RunStatus.WAITING_INPUT
                or origin_flow_run.canonical_status == FlowRunStatus.WAITING
            ):
                origin_graph_state = await self.repository.get_graph_state(
                    origin_flow_run_id
                )
                if origin_graph_state is not None:
                    try:
                        snapshot = _GraphStateSnapshot.model_validate(
                            origin_graph_state.state or {}
                        )
                    except ValidationError as exc:
                        raise DomainValidationException(
                            message="invalid_graph_state"
                        ) from exc
                    origin_start_node_id = (
                        snapshot.resume_to_node_id or snapshot.current_node_id
                    )
                    origin_initial_state = snapshot.state
                    origin_initial_memory = snapshot.memory
                else:
                    origin_flow_run_id = None
            else:
                origin_flow_run_id = None
        graph_snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(
            selected_flow_version_id
        )
        if graph_snapshot is None:
            raise ResourceBlockedServiceException(message="flow_graph_snapshot_missing")

        runtime_policy = await self.policy_resolver.resolve(
            tenant_id=tenant_id, flow_id=flow_id
        )
        runtime_policy_hash = self._hash_dict(runtime_policy.definition.model_dump())
        execution_plan_hash = graph_snapshot.graph_hash
        tool_catalog_hash = self._hash_dict(
            {"graph": execution_plan_hash, "runtime_policy": runtime_policy_hash}
        )
        llm_provider_config_hash = None

        flow_run_id = await self.repository.create_flow_run(
            session_id=flow_run.session_id,
            flow_version_id=selected_flow_version_id,
            correlation_id=correlation_id,
            origin_flow_run_id=origin_flow_run_id,
            user_id=flow_run.user_id,
            input_payload=flow_run.input,
            interaction_id=interaction_id,
            flow_graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
            runtime_policy_hash=runtime_policy_hash,
            tool_catalog_hash=tool_catalog_hash,
            llm_provider_config_hash=llm_provider_config_hash,
            trace_id=trace_uuid,
            root_observation_id=None,
        )

        with self.tracer.observe(
            as_type="event",
            name="domain.execution.execution_service.start_flow_trace",
            input={"flow_run_id": str(flow_run_id), "flow_id": str(flow_id)},
        ) as event_handle:
            trace_context: TraceContext = self.tracer.start_flow_trace(
                flow_run_id=flow_run_id,
                flow_id=flow_id,
                flow_version_id=selected_flow_version_id,
                tenant_id=tenant_id,
                session_id=flow_run.session_id,
                user_id=flow_run.user_id,
                external_request_id=request_id,
                trace_id=trace_uuid,
                interaction_id=interaction_id,
                correlation_id=correlation_id,
                channel=channel,
                external_message_id=external_message_id,
                graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
                execution_plan_hash=execution_plan_hash,
                flow_name=flow.name if flow else None,
            )
            if event_handle:
                event_handle.success(
                    output={"trace_context": trace_context.model_dump(mode="json")}
                )
        if trace_context.root_observation_id:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.execution_service.set_root_observation_id",
                input={
                    "flow_run_id": str(flow_run_id),
                    "root_observation_id": trace_context.root_observation_id or "",
                },
            ):
                await self.repository.set_root_observation_id(
                    flow_run_id=flow_run_id,
                    root_observation_id=trace_context.root_observation_id,
                )

        await self.repository.link_interaction_to_flow_run(
            interaction_id=interaction_id, flow_run_id=flow_run_id
        )
        self.repository.start_event_batching(flow_run_id)
        # canonical status: CREATED
        response = FlowRun(
            id=flow_run_id,
            origin_flow_run_id=origin_flow_run_id,
            flow_version_id=selected_flow_version_id,
            session_id=flow_run.session_id,
            user_id=flow_run.user_id,
            interaction_id=interaction_id,
            status=RunStatus.CREATED,
            canonical_status=FlowRunStatus.CREATED,
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            input=flow_run.input.model_dump(mode="json"),
            output={},
            error={},
            trace_id=trace_uuid,
            root_observation_id=None,
            flow_graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
            runtime_policy_hash=runtime_policy_hash,
            tool_catalog_hash=tool_catalog_hash,
            llm_provider_config_hash=llm_provider_config_hash,
        )
        with self.tracer.observe(
            as_type="event",
            name="domain.execution.execution_service.on_flow_start",
            input={
                "flow_run_id": str(flow_run_id),
                "correlation_id": str(correlation_id),
            },
        ) as event_handle:
            payload = {
                "interaction_id": str(interaction_id),
                "channel": channel,
                "trace_id": str(trace_uuid),
                "user_id": flow_run.user_id,
            }
            await self.hook.on_flow_start(
                tenant_id=tenant_id,
                user_id=flow_run.user_id,
                session_id=flow_run.session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                payload=payload,
                causation_id=None,
                schema_version=1,
            )
            if event_handle:
                event_handle.success(output={"status": "recorded", "payload": payload})
        available_tools: list[
            AvailableTool
        ] = await self.tools_service.list_available_tools_for_execution(
            tenant_id=tenant_id
        )

        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.execution_service.cache_get_plan",
            input={"graph_hash": graph_snapshot.graph_hash},
        ) as retriever_handle:
            cached_plan = await self.cache_adapter.get(graph_snapshot.graph_hash)
            if retriever_handle:
                retriever_handle.success(output={"cached_plan": cached_plan})
        if cached_plan:
            plan: ExecutionPlan = ExecutionPlan.model_validate(cached_plan)
        else:
            plan = self.plan_compiler.compile(
                graph_snapshot.snapshot,
                graph_snapshot.graph_hash,
                available_tools=available_tools,
            )
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.execution_service.cache_set_plan",
                input={"graph_hash": graph_snapshot.graph_hash},
            ) as tool_handle:
                await self.cache_adapter.set(
                    graph_snapshot.graph_hash, plan.model_dump(mode="json")
                )
                if tool_handle:
                    tool_handle.success(
                        output={
                            "key": graph_snapshot.graph_hash,
                            "plan": plan.model_dump(mode="json"),
                        }
                    )

        flow_handle = None
        flow_run_result = None
        try:
            with self.tracer.flow(
                trace=trace_context,
                input={"user_input": flow_run.input.user_input},
            ) as flow_handle:
                with self.tracer.observe(
                    as_type="chain",
                    name="flow.execution",
                    input={"plan_hash": execution_plan_hash, "node_count": len(plan.nodes)},
                    metadata={"chain_name": "flow.execution"},
                ) as chain_handle:
                    await self.runtime.run(
                        tenant_id=tenant_id,
                        session_id=flow_run.session_id,
                        input_payload=flow_run.input,
                        flow_id=flow_id,
                        flow_version_id=selected_flow_version_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        trace_id=trace_uuid,
                        plan=plan,
                        runtime_policy=runtime_policy,
                        trace_context=trace_context,
                        start_node_id=origin_start_node_id,
                        initial_state=origin_initial_state,
                        initial_memory=origin_initial_memory,
                    )
                    if chain_handle:
                        chain_handle.success(
                            output={
                                "plan_hash": execution_plan_hash,
                                "node_count": len(plan.nodes),
                            }
                        )
                if trace_context.root_observation_id:
                    await self.repository.set_root_observation_id(
                        flow_run_id=flow_run_id,
                        root_observation_id=trace_context.root_observation_id,
                    )

                flow_run_result = await self.repository.get_flow_run(flow_run_id)
                output = flow_run_result.output if flow_run_result else {}
                error = flow_run_result.error if flow_run_result else {}
                if flow_handle:
                    if error:
                        flow_handle.error(
                            error_type="flow_run_failed",
                            error_message=str(error),
                            output={"output": output, "error": error},
                        )
                    else:
                        flow_handle.success(output=output)
        finally:
            await self.repository.end_event_batching(flow_run_id)

        if flow_run_result:
            response = response.model_copy(
                update={
                    "status": RunStatus(flow_run_result.status),
                    "canonical_status": FlowRunStatus(flow_run_result.canonical_status),
                    "started_at": flow_run_result.started_at.isoformat()
                    if flow_run_result.started_at
                    else None,
                    "finished_at": flow_run_result.finished_at.isoformat()
                    if flow_run_result.finished_at
                    else None,
                    "output": flow_run_result.output or {},
                    "error": flow_run_result.error or {},
                    "root_observation_id": flow_run_result.root_observation_id,
                }
            )

        await self.idempotency.set_result(
            key,
            {
                "flow_run_id": str(flow_run_id),
                "response": response.model_dump(),
            },
        )
        return response

    async def resume_flow_run(
        self,
        *,
        flow_run_id: UUID,
        input_payload: FlowRunResumeInput | None,
        channel: str,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> FlowRun:
        if input_payload is None:
            raise DomainValidationException(message="user_id_required")
        user_id = input_payload.user_id

        flow_run = await self.repository.get_flow_run(flow_run_id)
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")
        if flow_run.user_id != user_id:
            raise DomainConflictException(message="session_user_mismatch")

        session_id, tenant_id = await self.repository.get_flow_context(flow_run_id)

        graph_state = await self.repository.get_graph_state(flow_run_id)
        if graph_state is None:
            raise NotFoundServiceException(message="graph_state_not_found")

        flow_version = await self.repository.get_flow_version(flow_run.flow_version_id)
        if flow_version is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        flow_id = flow_version.flow_id

        graph_snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(
            flow_version.flow_version_id
        )
        if graph_snapshot is None:
            raise NotFoundServiceException(message="flow_graph_snapshot_not_found")

        available_tools: list[
            AvailableTool
        ] = await self.tools_service.list_available_tools_for_execution(
            tenant_id=tenant_id
        )

        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.execution_service.cache_get_plan_resume",
            input={"graph_hash": graph_snapshot.graph_hash},
        ):
            cached_plan = await self.cache_adapter.get(graph_snapshot.graph_hash)
        if cached_plan:
            plan: ExecutionPlan = ExecutionPlan.model_validate(cached_plan)
        else:
            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.execution_service.compile_plan_resume",
                input={
                    "graph_hash": graph_snapshot.graph_hash,
                    "tool_count": len(available_tools),
                },
            ):
                plan = self.plan_compiler.compile(
                    graph_snapshot.snapshot,
                    graph_snapshot.graph_hash,
                    available_tools=available_tools,
                )
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.execution_service.cache_set_plan_resume",
                input={"graph_hash": graph_snapshot.graph_hash},
            ):
                await self.cache_adapter.set(
                    graph_snapshot.graph_hash, plan.model_dump(mode="json")
                )

        runtime_policy = await self.policy_resolver.resolve(
            tenant_id=tenant_id, flow_id=flow_id
        )

        interaction_id = await self.repository.create_interaction(
            session_id=session_id,
            channel=channel,
            payload={"resume_input": input_payload.model_dump(mode="json")},
            headers=headers,
            metadata={},
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=trace_id,
        )

        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.execution_service.link_interaction_to_flow_run_resume",
            input={
                "flow_run_id": str(flow_run_id),
                "interaction_id": str(interaction_id),
            },
        ):
            await self.repository.link_interaction_to_flow_run(
                interaction_id=interaction_id, flow_run_id=flow_run_id
            )

        trace_uuid = UUID(trace_id) if trace_id else flow_run.trace_id or uuid4()

        with self.tracer.observe(
            as_type="event",
            name="domain.execution.execution_service.start_flow_resume_trace",
            input={"flow_run_id": str(flow_run_id), "flow_id": str(flow_id)},
        ):
            trace_context: TraceContext = self.tracer.start_flow_trace(
                flow_run_id=flow_run_id,
                flow_id=flow_id,
                flow_version_id=flow_version.flow_version_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                external_request_id=request_id,
                trace_id=trace_uuid,
                interaction_id=interaction_id,
                correlation_id=flow_run.correlation_id,
                channel=channel,
                external_message_id=external_message_id,
                graph_snapshot_id=graph_snapshot.flow_graph_snapshot_id,
            )

        if trace_context.root_observation_id:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.execution_service.set_root_observation_id_resume",
                input={
                    "flow_run_id": str(flow_run_id),
                    "root_observation_id": trace_context.root_observation_id or "",
                },
            ):
                await self.repository.set_root_observation_id(
                    flow_run_id=flow_run_id,
                    root_observation_id=trace_context.root_observation_id,
                )

        await self.repository.set_flow_run_status(
            flow_run_id=flow_run_id,
            status=RunStatus.RUNNING,
            canonical_status=FlowRunStatus.RUNNING,
        )

        try:
            snapshot = _GraphStateSnapshot.model_validate(graph_state.state or {})
        except ValidationError as exc:
            raise DomainValidationException(message="invalid_graph_state") from exc
        resume_to_node_id = snapshot.resume_to_node_id or snapshot.current_node_id
        initial_state = snapshot.state
        initial_memory = snapshot.memory

        self.repository.start_event_batching(flow_run_id)
        try:
            with self.tracer.flow(
                trace=trace_context,
                input={"user_input": input_payload.user_input},
            ):
                await self.runtime.run(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    input_payload=FlowRunInput(user_input=input_payload.user_input),
                    flow_id=flow_id,
                    flow_version_id=flow_version.flow_version_id,
                    flow_run_id=flow_run_id,
                    correlation_id=flow_run.correlation_id,
                    trace_id=trace_uuid,
                    plan=plan,
                    runtime_policy=runtime_policy,
                    trace_context=trace_context,
                    start_node_id=resume_to_node_id,
                    initial_state=initial_state,
                    initial_memory=initial_memory,
                )

            flow_run_result = await self.repository.get_flow_run(flow_run_id)
            if flow_run_result is None:
                raise NotFoundServiceException(message="flow_run_not_found")
            return FlowRun.from_model(flow_run_result)
        finally:
            await self.repository.end_event_batching(flow_run_id)

    async def create_agent_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        agent_run: AgentRunCreate,
    ) -> AgentRun:
        node_run = await self.repository.get_node_run(agent_run.node_run_id)
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
                correlation_id=agent_run.correlation_id or uuid4(),
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

        agent_version = await self.repository.get_agent_version(
            agent_run.agent_version_id
        )
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        if agent_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="agent_version_blocked")
        active_agent_version_id = await self.repository.get_active_agent_version_id(
            agent_version.agent_id
        )
        if (
            active_agent_version_id is None
            or active_agent_version_id != agent_run.agent_version_id
        ):
            raise ResourceBlockedServiceException(message="agent_version_not_active")

        policy_version = await self.repository.get_ai_execution_policy_version(
            agent_run.ai_execution_policy_version_id
        )
        if policy_version is None:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        if policy_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="ai_execution_policy_blocked")
        if agent_version.ai_execution_policy_version_id and (
            agent_version.ai_execution_policy_version_id
            != agent_run.ai_execution_policy_version_id
        ):
            raise DomainConflictException(message="ai_execution_policy_mismatch")

        model_record = await self.repository.get_model(policy_version.model_id)
        model_name = model_record.name if model_record else None

        if agent_version.rag_config_id and not bool(ai_task.allow_rag_tenant):
            raise RagNotAllowedException(message="rag_not_allowed_for_task")

        billing_policy_version_id = (
            await self.repository.get_active_billing_policy_version_id(tenant_id)
        )
        if billing_policy_version_id is None:
            raise ResourceBlockedServiceException(message="billing_policy_not_active")

        system_prompt_hash = None
        if agent_version.system_prompt_template_id:
            template = await self.prompt_repository.get_system_prompt_template(
                agent_version.system_prompt_template_id
            )
            if template is None:
                raise NotFoundServiceException(
                    message="system_prompt_template_not_found"
                )

            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )

            system_prompt = self.system_prompt_compiler.render(template, persona)
            system_prompt_hash = self.system_prompt_compiler.compute_hash(system_prompt)

        key = self.idempotency.build_key(
            tenant_id=tenant_id, endpoint=endpoint, idempotency_key=idempotency_key
        )
        acquired = await self.idempotency.try_acquire(key)
        if not acquired:
            existing = await self.idempotency.get(key)
            if existing and "response" in existing:
                return AgentRun.model_validate(existing["response"])
            raise IdempotencyInProgressException()

        correlation_id = agent_run.correlation_id or uuid4()
        agent_run_id = await self.repository.create_agent_run(
            ai_task_id=node.ai_task_id,
            node_run_id=agent_run.node_run_id,
            agent_version_id=agent_run.agent_version_id,
            ai_execution_policy_version_id=agent_run.ai_execution_policy_version_id,
            correlation_id=correlation_id,
            input_payload=agent_run.input,
            model=model_name,
            billing_policy_version_id=billing_policy_version_id,
            system_prompt_hash=system_prompt_hash,
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
                "node_run_id": str(agent_run.node_run_id),
                "ai_task_id": str(node.ai_task_id),
                "agent_version_id": str(agent_run.agent_version_id),
                "policy_version_id": str(agent_run.ai_execution_policy_version_id),
                "billing_policy_version_id": str(billing_policy_version_id),
                "model": model_name,
            },
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
        )

        response = AgentRun(
            id=agent_run_id,
            node_run_id=agent_run.node_run_id,
            ai_task_id=node.ai_task_id,
            agent_version_id=agent_run.agent_version_id,
            ai_execution_policy_version_id=agent_run.ai_execution_policy_version_id,
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
            input=agent_run.input,
            output={},
            error={},
            system_prompt_hash=system_prompt_hash,
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
        (node_run.flow_run_id if node_run else raw_output.get("flow_run_id"))
        normalized_output = raw_output
        try:
            if (
                output_schema
                and isinstance(output_schema, type)
                and issubclass(output_schema, BaseModel)
            ):
                normalized_output = output_schema.model_validate(
                    raw_output
                ).model_dump()
        except ValidationError as exc:
            if node_run is None:
                raise DomainValidationException(message="node_run_not_found")
            session_id, tenant_id = await self.repository.get_flow_context(
                node_run.flow_run_id
            )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=node_run.flow_run_id,
                event_type=ExecutionEventType.AgentRunFailed,
                payload={
                    "agent_run_id": str(agent_run_id),
                    "policy_version_id": str(
                        existing_agent_run.ai_execution_policy_version_id
                    ),
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
            raise AIOutputValidationException(
                message="ai_output_validation_failed", detail=exc.errors()
            ) from exc

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
        session_id, tenant_id = await self.repository.get_flow_context(
            node_run.flow_run_id
        )
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=node_run.flow_run_id,
            event_type=ExecutionEventType.AgentRunCompleted,
            payload={
                "agent_run_id": str(agent_run_id),
                "agent_version_id": str(existing_agent_run.agent_version_id),
                "policy_version_id": str(
                    existing_agent_run.ai_execution_policy_version_id
                ),
                "ai_task_id": str(existing_agent_run.ai_task_id)
                if existing_agent_run.ai_task_id
                else None,
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
        tool_run: ToolRunCreate,
    ) -> ToolRun:
        if tool_run.node_run_id is None and tool_run.agent_run_id is None:
            raise DomainValidationException(message="tool_run_missing_parent")

        billing_policy_version_id = (
            await self.repository.get_active_billing_policy_version_id(tenant_id)
        )
        if billing_policy_version_id is None:
            raise ResourceBlockedServiceException(message="billing_policy_not_active")

        if tool_run.node_run_id:
            node_run = await self.repository.get_node_run(tool_run.node_run_id)
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
                    correlation_id=tool_run.correlation_id or uuid4(),
                    causation_id=None,
                    schema_version=1,
                )
                raise
        else:
            agent_run_id = tool_run.agent_run_id
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
                    correlation_id=tool_run.correlation_id or uuid4(),
                    causation_id=None,
                    schema_version=1,
                )
                raise

        tool_config = await self.repository.get_tool_config(tool_run.tool_config_id)
        if tool_config is None:
            raise NotFoundServiceException(message="tool_config_not_found")
        if tool_config.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="tool_config_blocked")

        if tool_run.agent_run_id:
            agent_run = await self.repository.get_agent_run(tool_run.agent_run_id)
            if agent_run is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            agent_version = await self.repository.get_agent_version(
                agent_run.agent_version_id
            )
            if agent_version is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            if (
                agent_version.supported_tool_schema_version is not None
                and tool_config.schema_version is not None
                and agent_version.supported_tool_schema_version
                != tool_config.schema_version
            ):
                raise SchemaIncompatibleException(
                    message="tool_config_schema_incompatible"
                )
            if (
                agent_version.supported_tool_config_hash_prefix
                and tool_config.config_hash
                and not tool_config.config_hash.startswith(
                    agent_version.supported_tool_config_hash_prefix
                )
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

        correlation_id = tool_run.correlation_id or uuid4()
        tool_run_id = await self.repository.create_tool_run(
            tool_config_id=tool_run.tool_config_id,
            correlation_id=correlation_id,
            agent_run_id=tool_run.agent_run_id,
            node_run_id=tool_run.node_run_id,
            idempotency_key=idempotency_key,
            has_side_effect=tool_run.has_side_effect,
            input_payload=tool_run.input,
            estimated_cost=None,
            billing_policy_version_id=billing_policy_version_id,
        )
        response = ToolRun(
            id=tool_run_id,
            tool_config_id=tool_run.tool_config_id,
            agent_run_id=tool_run.agent_run_id,
            node_run_id=tool_run.node_run_id,
            status=RunStatus.CREATED,
            correlation_id=correlation_id,
            started_at=None,
            finished_at=None,
            input=tool_run.input,
            output={},
            error={},
            idempotency_key=idempotency_key,
            has_side_effect=tool_run.has_side_effect,
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
                "tool_config_id": str(tool_run.tool_config_id),
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

    async def get_flow_run(self, flow_run_id: str) -> FlowRun:
        result = await self.repository.get_flow_run(UUID(flow_run_id))
        if result is None:
            raise NotFoundServiceException(message="flow_run_not_found")

        failure_reason = None
        all_events = await self.repository.list_execution_events(
            flow_run_id=UUID(flow_run_id),
            correlation_id=None,
            limit=200,
        )
        for event in reversed(all_events):
            if event.type == ExecutionEventType.FlowFailed:
                reason_str = (
                    event.tool_run.get("reason")
                    if isinstance(event.payload, dict)
                    else None
                )
                if reason_str:
                    try:
                        failure_reason = FlowFailureReason(reason_str)
                    except ValueError:
                        pass
                break

        return FlowRun.from_model(result, failure_reason=failure_reason)

    async def get_graph_state(self, flow_run_id: str) -> GraphState:
        flow_run = await self.repository.get_flow_run(UUID(flow_run_id))
        if flow_run is None:
            raise NotFoundServiceException(message="flow_run_not_found")

        graph_state = await self.repository.get_graph_state(UUID(flow_run_id))
        if graph_state is None:
            raise NotFoundServiceException(message="graph_state_not_found")

        return GraphState(
            id=graph_state.graph_state_id,
            flow_run_id=graph_state.flow_run_id,
            state=graph_state.state,
            last_node_run_id=graph_state.last_node_run_id,
        )

    async def list_node_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[NodeRun]:
        node_runs = await self.repository.list_node_runs(
            tenant_id=tenant_id, flow_run_id=flow_run_id, limit=limit
        )
        return [
            NodeRun(
                id=node_run.node_run_id,
                flow_run_id=node_run.flow_run_id,
                node_id=node_run.node_id,
                status=node_run.status,
                canonical_status=node_run.canonical_status,
                correlation_id=node_run.correlation_id,
                started_at=node_run.started_at.isoformat()
                if node_run.started_at
                else None,
                finished_at=node_run.finished_at.isoformat()
                if node_run.finished_at
                else None,
                input=node_run.input,
                output=node_run.output,
                error=node_run.error,
            )
            for node_run in node_runs
        ]

    async def list_agent_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRun]:
        agent_runs = await self.repository.list_agent_runs(
            tenant_id=tenant_id, flow_run_id=flow_run_id, limit=limit
        )
        return [
            AgentRun(
                id=agent_run.agent_run_id,
                node_run_id=agent_run.node_run_id,
                ai_task_id=agent_run.ai_task_id,
                agent_version_id=agent_run.agent_version_id,
                ai_execution_policy_version_id=agent_run.ai_execution_policy_version_id,
                billing_policy_version_id=agent_run.billing_policy_version_id,
                model=agent_run.model,
                input_tokens=agent_run.input_tokens,
                output_tokens=agent_run.output_tokens,
                estimated_cost=float(agent_run.estimated_cost)
                if agent_run.estimated_cost is not None
                else None,
                status=agent_run.status,
                canonical_status=agent_run.canonical_status,
                correlation_id=agent_run.correlation_id,
                started_at=agent_run.started_at.isoformat()
                if agent_run.started_at
                else None,
                finished_at=agent_run.finished_at.isoformat()
                if agent_run.finished_at
                else None,
                input=agent_run.input,
                output=agent_run.output,
                error=agent_run.error,
            )
            for agent_run in agent_runs
        ]

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
                user_id=e.user_id,
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
