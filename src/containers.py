from dependency_injector import containers, providers

import settings
from openai import AsyncOpenAI
from adapters.cache.redis_adapter import RedisAdapter
from adapters.secrets.env_secret_resolver import EnvSecretResolver
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.adapters.slm_local_provider import SLMLocalProvider
from domain.llm.adapters.moderation_openai_adapter import ModerationOpenAIAdapter
from domain.llm.adapters.moderation_slm_adapter import ModerationSLMAdapter
from domain.llm.services.moderation_orchestration_service import (
    ModerationOrchestrationService,
)
from infra.database import DatabaseConnection, async_session, engine

from domain.auth.controllers.auth_controller import AuthController
from domain.auth.services.auth_service import AuthService
from domain.tenants.controllers.tenants_controller import TenantsController
from domain.tenants.repositories.tenant_summary_repository import (
    TenantSummaryRepository,
)
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.tenants.services.tenant_summary_service import TenantSummaryService
from domain.tenants.services.tenants_service import TenantsService
from domain.flows.controllers.flows_controller import FlowsController
from domain.flows.services.flows_service import FlowsService
from domain.flows.repositories.flows_repository import FlowsRepository
from domain.agents.controllers.agents_controller import AgentsController
from domain.agents.services.agents_service import AgentsService
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.tools.controllers.tools_controller import ToolsController
from domain.tools.services.tools_service import ToolsService
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from domain.ai_policy.controllers.ai_controller import AIController
from domain.ai_policy.services.ai_service import AIService
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.rag.controllers.rag_controller import RagController
from domain.rag.services.rag_service import RagService
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.rag.repositories.rag_repository import RagRepository
from domain.execution.controllers.execution_controller import ExecutionController
from domain.execution.controllers.execution_plane_controller import (
    ExecutionPlaneController,
)
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.execution.adapters.idempotency_service import IdempotencyService
from services.execution_boundary import ExecutionBoundary
from infra.http_tool_executor import HttpToolExecutor
from domain.governance.repositories.access_policy_repository import (
    AccessPolicyRepository,
)
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.governance.services.execution_limit_service import ExecutionLimitService
from domain.governance.repositories.rate_limit_policy_repository import (
    RateLimitPolicyRepository,
)
from domain.governance.services.rate_limit_service import RateLimitService
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.governance.controllers.llm_admin_controller import LLMAdminController
from domain.governance.controllers.governance_policies_controller import (
    GovernancePoliciesController,
)
from domain.governance.repositories.llm_provider_repository import LLMProviderRepository
from domain.governance.repositories.llm_model_mapping_repository import (
    LLMModelMappingRepository,
)
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.governance.services.llm_admin_service import LLMAdminService
from domain.governance.repositories.runtime_policy_repository import (
    RuntimePolicyRepository,
)
from domain.governance.repositories.billing_policy_repository import (
    BillingPolicyRepository,
)
from domain.governance.repositories.memory_policy_repository import (
    MemoryPolicyRepository,
)
from domain.governance.repositories.rag_policy_repository import RagPolicyRepository
from domain.governance.services.governance_policies_service import (
    GovernancePoliciesService,
)
from domain.onboarding.controllers.onboarding_controller import OnboardingController
from domain.onboarding.services.onboarding_service import OnboardingService
from domain.onboarding.repositories.onboarding_repository import OnboardingRepository
from domain.prompts.controllers.prompt_controller import PromptController
from domain.prompts.services.prompt_service import PromptService
from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.user_prompts.controllers.user_prompts_controller import (
    UserPromptsController,
)
from domain.user_prompts.repositories.user_prompts_repository import (
    UserPromptsRepository,
)
from domain.user_prompts.services.user_prompts_service import UserPromptsService
from domain.mcp_registry.repositories.mcp_registry_repository import (
    McpRegistryRepository,
)
from domain.mcp_registry.services.mcp_registry_service import McpRegistryService
from domain.mcp_registry.controllers.mcp_registry_controller import (
    McpRegistryController,
)
from domain.conversation.controllers.conversation_controller import (
    ConversationController,
)
from domain.conversation.controllers.conversation_read_controller import (
    ConversationReadController,
)
from domain.conversation.repositories.conversation_read_repository import (
    ConversationReadRepository,
)
from domain.conversation.services.conversation_read_service import (
    ConversationReadService,
)
from domain.conversation.services.conversation_service import ConversationService
from domain.human_sla.controllers.human_sla_controller import HumanSLAController
from domain.human_sla.repositories.human_sla_policy_repository import (
    HumanSLAPolicyRepository,
)
from domain.human_sla.repositories.human_sla_repository import HumanSLARepository
from domain.human_sla.services.human_sla_service import HumanSLAService
from services.conversation_boundary import ConversationBoundary


class CoreContainer(containers.DeclarativeContainer):
    engine_provider = providers.Object(engine)
    async_session_provider = providers.Object(async_session)

    database_connection = providers.Singleton(
        DatabaseConnection,
        engine=engine_provider,
        sessionmaker=async_session_provider,
    )


class AdaptersContainer(containers.DeclarativeContainer):
    redis_adapter = providers.Singleton(
        RedisAdapter,
        silent_mode=settings.CACHE_SILENT_MODE,
    )
    secret_resolver = providers.Singleton(EnvSecretResolver)
    tracer = providers.Singleton(LangfuseRuntimeTracer)

    openai_client = providers.Singleton(AsyncOpenAI, api_key=settings.OPENAI_API_KEY)

    openai_provider = providers.Singleton(
        OpenAIProviderAdapter,
        cache_adapter=redis_adapter,
        openai_client=openai_client,
    )
    slm_local_provider = providers.Singleton(
        SLMLocalProvider,
        credential_secret_ref=None,
    )


class TenantSummaryContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    agents = providers.DependenciesContainer()
    flows = providers.DependenciesContainer()
    governance = providers.DependenciesContainer()
    tools = providers.DependenciesContainer()
    rag = providers.DependenciesContainer()
    ai_policy = providers.DependenciesContainer()
    human_sla = providers.DependenciesContainer()

    tenants_repository = providers.Factory(
        TenantsRepository,
        database_connection=core.database_connection,
    )
    tenant_summary_repository = providers.Factory(
        TenantSummaryRepository,
        database_connection=core.database_connection,
    )
    tenant_summary_service = providers.Factory(
        TenantSummaryService,
        tenants_repository=tenants_repository,
        agents_repository=agents.agents_repository,
        governance_policies_service=governance.governance_policies_service,
        tenant_summary_repository=tenant_summary_repository,
        tools_repository=tools.tools_repository,
        rag_repository=rag.rag_repository,
        human_sla_policy_repository=human_sla.human_sla_policy_repository,
        ai_service=ai_policy.ai_service,
        ai_repository=ai_policy.ai_repository,
        execution_limit_policy_repository=flows.execution_limit_policy_repository,
    )


class TenantsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    summary_service = providers.Dependency()

    tenants_repository = providers.Factory(
        TenantsRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    tenants_service = providers.Factory(
        TenantsService,
        repository=tenants_repository,
        authoring_events=authoring_event_repository,
    )
    tenants_controller = providers.Factory(
        TenantsController,
        service=tenants_service,
        summary_service=summary_service,
    )


class AuthContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    tenants_repository = providers.Factory(
        TenantsRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    auth_service = providers.Factory(
        AuthService,
        tenants_repository=tenants_repository,
        authoring_event_repository=authoring_event_repository,
    )
    auth_controller = providers.Factory(AuthController, service=auth_service)


class FlowsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    rag = providers.DependenciesContainer()

    flows_repository = providers.Factory(
        FlowsRepository,
        database_connection=core.database_connection,
    )
    execution_limit_policy_repository = providers.Factory(
        ExecutionLimitPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    flows_idempotency_service = providers.Factory(
        IdempotencyService,
        redis_adapter=adapters.redis_adapter,
        tracer=adapters.tracer,
    )
    flows_service = providers.Factory(
        FlowsService,
        repository=flows_repository,
        limit_policy_repository=execution_limit_policy_repository,
        authoring_events=authoring_event_repository,
        idempotency=flows_idempotency_service,
        rag_repository=rag.rag_repository,
        rag_policy_service=rag.rag_policy_service,
    )
    flows_controller = providers.Factory(FlowsController, service=flows_service)


class AgentsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    agents_repository = providers.Factory(
        AgentsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    agents_service = providers.Factory(
        AgentsService,
        repository=agents_repository,
        authoring_events=authoring_event_repository,
    )
    agents_controller = providers.Factory(AgentsController, service=agents_service)


class ToolsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    tools_repository = providers.Factory(
        ToolsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    agents_repository = providers.Factory(
        AgentsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    tools_service = providers.Factory(
        ToolsService,
        repository=tools_repository,
        agents_repository=agents_repository,
        authoring_events=authoring_event_repository,
        tracer=adapters.tracer,
    )
    tools_controller = providers.Factory(ToolsController, service=tools_service)


class AIPolicyContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    ai_repository = providers.Factory(
        AIRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    ai_service = providers.Factory(
        AIService,
        repository=ai_repository,
        authoring_events=authoring_event_repository,
    )
    ai_controller = providers.Factory(AIController, service=ai_service)


class RAGContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    rag_repository = providers.Factory(
        RagRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    rag_execution_repository = providers.Factory(
        ExecutionRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    rag_policy_service = providers.Factory(
        RagPolicyService,
        repository=rag_execution_repository,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    ai_repository = providers.Factory(
        AIRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    rag_service = providers.Factory(
        RagService,
        repository=rag_repository,
        authoring_events=authoring_event_repository,
    )
    embedding_adapter = providers.Factory(
        OpenAIEmbeddingAdapter,
        api_key=settings.OPENAI_API_KEY,
        model="text-embedding-3-small",
        dimension=settings.EMBEDDING_DIMENSION,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    rag_runtime_service = providers.Factory(
        RagRuntimeService,
        repository=rag_repository,
        embedding_adapter=embedding_adapter,
        tracer=adapters.tracer,
        rag_policy_service=rag_policy_service,
        ai_repository=ai_repository,
    )
    rag_controller = providers.Factory(
        RagController, service=rag_service, runtime_service=rag_runtime_service
    )


class HumanSLAContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()

    human_sla_repository = providers.Factory(
        HumanSLARepository,
        database_connection=core.database_connection,
    )
    human_sla_policy_repository = providers.Factory(
        HumanSLAPolicyRepository,
        database_connection=core.database_connection,
    )
    human_sla_service = providers.Factory(
        HumanSLAService,
        repository=human_sla_repository,
        policy_repository=human_sla_policy_repository,
    )
    human_sla_controller = providers.Factory(
        HumanSLAController,
        service=human_sla_service,
    )


class ExecutionContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    tools = providers.DependenciesContainer()
    human_sla = providers.DependenciesContainer()

    access_policy_repository = providers.Factory(
        AccessPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    access_policy_service = providers.Factory(
        AccessPolicyService,
        repository=access_policy_repository,
        tracer=adapters.tracer,
    )
    rate_limit_policy_repository = providers.Factory(
        RateLimitPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    rate_limit_service = providers.Factory(
        RateLimitService,
        repository=rate_limit_policy_repository,
        redis_adapter=adapters.redis_adapter,
        tracer=adapters.tracer,
    )
    execution_limit_policy_repository = providers.Factory(
        ExecutionLimitPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    execution_repository = providers.Factory(
        ExecutionRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    prompt_repository = providers.Factory(
        PromptRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    prompt_service = providers.Factory(
        PromptService,
        repository=prompt_repository,
        execution_repository=execution_repository,
        tracer=adapters.tracer,
    )
    moderation_default_config = providers.Object(
        {
            "primary": {
                "provider": "SLM_LOCAL",
                "model_alias": "slm-local-moderation",
                "timeout_ms": 300,
            },
            "fallback": {
                "provider": "OPENAI",
                "model_alias": settings.OPENAI_MODERATION_MODEL,
                "timeout_ms": 1000,
            },
            "fallback_enabled": True,
            "prompt_key": "ContentModeration",
            "temperature": 0.0,
            "max_tokens": 18,
        }
    )
    openai_moderation_adapter = providers.Factory(
        ModerationOpenAIAdapter,
        client=adapters.openai_client,
        cache_adapter=adapters.redis_adapter,
        tracer=adapters.tracer,
        model=settings.OPENAI_MODERATION_MODEL,
        timeout=1,
    )
    slm_moderation_adapter = providers.Factory(
        ModerationSLMAdapter,
        slm_provider=adapters.slm_local_provider,
        prompt_text=None,
        output_schema=None,
        prompt_service=prompt_service,
        prompt_key="ContentModeration",
        model_alias="slm-local-moderation",
        slm_timeout_s=0.3,
        temperature=0.0,
        max_tokens=18,
    )
    moderation_orchestration_service = providers.Factory(
        ModerationOrchestrationService,
        slm_provider=slm_moderation_adapter,
        openai_provider=openai_moderation_adapter,
        default_config=moderation_default_config,
    )
    idempotency_service = providers.Factory(
        IdempotencyService,
        redis_adapter=adapters.redis_adapter,
        tracer=adapters.tracer,
    )
    lifecycle = providers.Singleton(
        RunLifecycleStateMachine,
        tracer=adapters.tracer,
    )
    execution_limit_service = providers.Factory(
        ExecutionLimitService,
        policy_repository=execution_limit_policy_repository,
        execution_repository=execution_repository,
    )
    execution_service = providers.Factory(
        ExecutionService,
        repository=execution_repository,
        idempotency=idempotency_service,
        lifecycle=lifecycle,
        limits=execution_limit_service,
        tracer=adapters.tracer,
        tools_service=tools.tools_service,
        openai_provider=adapters.openai_provider,
        slm_local_provider=adapters.slm_local_provider,
        secret_resolver=adapters.secret_resolver,
        llm_moderation_provider=moderation_orchestration_service,
        human_sla_service=human_sla.human_sla_service,
    )
    tool_executor = providers.Singleton(HttpToolExecutor, tracer=adapters.tracer)
    tool_orchestrator = providers.Factory(
        ToolOrchestrator,
        repository=execution_repository,
        executor=tool_executor,
        secret_resolver=adapters.secret_resolver,
        tracer=adapters.tracer,
        tools_repository=tools.tools_repository,
    )
    execution_boundary = providers.Factory(
        ExecutionBoundary,
        execution_service=execution_service,
        tool_orchestrator=tool_orchestrator,
        access_policy_service=access_policy_service,
        rate_limit_service=rate_limit_service,
    )
    execution_controller = providers.Factory(
        ExecutionController,
        boundary=execution_boundary,
        tracer=adapters.tracer,
    )
    execution_plane_controller = providers.Factory(
        ExecutionPlaneController,
        boundary=execution_boundary,
        tracer=adapters.tracer,
    )


class OnboardingContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    onboarding_repository = providers.Factory(
        OnboardingRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    onboarding_service = providers.Factory(
        OnboardingService,
        repository=onboarding_repository,
        authoring_events=authoring_event_repository,
    )
    onboarding_controller = providers.Factory(
        OnboardingController, service=onboarding_service
    )


class PromptsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    execution = providers.DependenciesContainer()

    prompt_repository = providers.Factory(
        PromptRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    prompt_service = providers.Factory(
        PromptService,
        repository=prompt_repository,
        execution_repository=execution.execution_repository,
        tracer=adapters.tracer,
    )
    prompt_controller = providers.Factory(PromptController, service=prompt_service)


class UserPromptsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    user_prompts_repository = providers.Factory(
        UserPromptsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    user_prompts_service = providers.Factory(
        UserPromptsService,
        repository=user_prompts_repository,
    )
    user_prompts_controller = providers.Factory(
        UserPromptsController,
        service=user_prompts_service,
    )


class ConversationContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    execution = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    user_prompts = providers.DependenciesContainer()

    conversation_read_repository = providers.Factory(
        ConversationReadRepository,
        database_connection=core.database_connection,
    )
    conversation_read_service = providers.Factory(
        ConversationReadService,
        read_repository=conversation_read_repository,
        execution_repository=execution.execution_repository,
    )
    conversation_read_controller = providers.Factory(
        ConversationReadController,
        service=conversation_read_service,
    )

    conversation_service = providers.Factory(
        ConversationService,
        execution_service=execution.execution_service,
        user_prompts_repository=user_prompts.user_prompts_repository,
    )
    conversation_boundary = providers.Factory(
        ConversationBoundary,
        conversation_service=conversation_service,
        access_policy_service=execution.access_policy_service,
        rate_limit_service=execution.rate_limit_service,
    )
    conversation_controller = providers.Factory(
        ConversationController,
        boundary=conversation_boundary,
        tracer=adapters.tracer,
    )


class McpRegistryContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()

    mcp_registry_repository = providers.Factory(
        McpRegistryRepository,
        database_connection=core.database_connection,
    )
    mcp_registry_service = providers.Factory(
        McpRegistryService,
        repository=mcp_registry_repository,
        public_base_url=providers.Object((settings.PUBLIC_BASE_URL or "").rstrip("/")),
    )
    mcp_registry_controller = providers.Factory(
        McpRegistryController,
        service=mcp_registry_service,
    )


class GovernanceContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    llm_provider_repository = providers.Factory(
        LLMProviderRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    llm_model_mapping_repository = providers.Factory(
        LLMModelMappingRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    llm_pricing_repository = providers.Factory(
        LLMPricingRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
        cache_adapter=adapters.redis_adapter,
    )
    ai_repository = providers.Factory(
        AIRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    llm_admin_service = providers.Factory(
        LLMAdminService,
        ai_repository=ai_repository,
        provider_repository=llm_provider_repository,
        mapping_repository=llm_model_mapping_repository,
        pricing_repository=llm_pricing_repository,
    )
    llm_admin_controller = providers.Factory(
        LLMAdminController,
        service=llm_admin_service,
    )
    runtime_policy_repository = providers.Factory(
        RuntimePolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    access_policy_repository = providers.Factory(
        AccessPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    rate_limit_policy_repository = providers.Factory(
        RateLimitPolicyRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
    )
    billing_policy_repository = providers.Factory(
        BillingPolicyRepository,
        database_connection=core.database_connection,
    )
    memory_policy_repository = providers.Factory(
        MemoryPolicyRepository,
        database_connection=core.database_connection,
    )
    rag_policy_repository = providers.Factory(
        RagPolicyRepository,
        database_connection=core.database_connection,
    )
    governance_policies_service = providers.Factory(
        GovernancePoliciesService,
        runtime_repository=runtime_policy_repository,
        access_repository=access_policy_repository,
        rate_limit_repository=rate_limit_policy_repository,
        billing_repository=billing_policy_repository,
        memory_repository=memory_policy_repository,
        rag_repository=rag_policy_repository,
    )
    governance_policies_controller = providers.Factory(
        GovernancePoliciesController,
        service=governance_policies_service,
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Application root container, grouping domain containers."""

    wiring_config = containers.WiringConfiguration(modules=[__name__])
    config = providers.Configuration()

    core = providers.Container(CoreContainer)
    adapters = providers.Container(AdaptersContainer)

    auth = providers.Container(AuthContainer, core=core, adapters=adapters)
    rag = providers.Container(RAGContainer, core=core, adapters=adapters)
    flows = providers.Container(FlowsContainer, core=core, adapters=adapters, rag=rag)
    agents = providers.Container(AgentsContainer, core=core, adapters=adapters)
    tools = providers.Container(ToolsContainer, core=core, adapters=adapters)
    ai_policy = providers.Container(AIPolicyContainer, core=core, adapters=adapters)
    human_sla = providers.Container(HumanSLAContainer, core=core)
    execution = providers.Container(
        ExecutionContainer,
        core=core,
        adapters=adapters,
        tools=tools,
        human_sla=human_sla,
    )
    onboarding = providers.Container(OnboardingContainer, core=core, adapters=adapters)
    prompts = providers.Container(
        PromptsContainer, core=core, adapters=adapters, execution=execution
    )
    user_prompts = providers.Container(
        UserPromptsContainer, core=core, adapters=adapters
    )
    conversation = providers.Container(
        ConversationContainer,
        core=core,
        execution=execution,
        adapters=adapters,
        user_prompts=user_prompts,
    )
    governance = providers.Container(GovernanceContainer, core=core, adapters=adapters)
    summary = providers.Container(
        TenantSummaryContainer,
        core=core,
        agents=agents,
        flows=flows,
        governance=governance,
        tools=tools,
        rag=rag,
        ai_policy=ai_policy,
        human_sla=human_sla,
    )
    tenants = providers.Container(
        TenantsContainer,
        core=core,
        adapters=adapters,
        summary_service=summary.tenant_summary_service,
    )
    mcp_registry = providers.Container(McpRegistryContainer, core=core)
