from dependency_injector import containers, providers

import settings
from adapters.cache.redis_adapter import RedisAdapter
from adapters.secrets.env_secret_resolver import EnvSecretResolver
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from infra.database import DatabaseConnection, async_session, engine

from domain.tenants.controllers.tenants_controller import TenantsController
from domain.tenants.services.tenants_service import TenantsService
from domain.tenants.repositories.tenants_repository import TenantsRepository
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
from domain.onboarding.controllers.onboarding_controller import OnboardingController
from domain.onboarding.services.onboarding_service import OnboardingService
from domain.onboarding.repositories.onboarding_repository import OnboardingRepository
from domain.prompts.controllers.prompt_controller import PromptController
from domain.prompts.services.prompt_service import PromptService
from domain.prompts.repositories.prompt_repository import PromptRepository


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


class TenantsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()

    tenants_repository = providers.Factory(
        TenantsRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
    )
    tenants_service = providers.Factory(
        TenantsService,
        repository=tenants_repository,
        authoring_events=authoring_event_repository,
    )
    tenants_controller = providers.Factory(TenantsController, service=tenants_service)


class FlowsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

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
    )
    flows_service = providers.Factory(
        FlowsService,
        repository=flows_repository,
        limit_policy_repository=execution_limit_policy_repository,
        authoring_events=authoring_event_repository,
    )
    flows_controller = providers.Factory(FlowsController, service=flows_service)


class AgentsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    agents_repository = providers.Factory(
        AgentsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
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
    )
    agents_repository = providers.Factory(
        AgentsRepository,
        database_connection=core.database_connection,
        tracer=adapters.tracer,
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
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
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
        dimension=1536,
        tracer=adapters.tracer,
    )
    rag_runtime_service = providers.Factory(
        RagRuntimeService,
        repository=rag_repository,
        embedding_adapter=embedding_adapter,
        tracer=adapters.tracer,
    )
    rag_controller = providers.Factory(
        RagController, service=rag_service, runtime_service=rag_runtime_service
    )


class ExecutionContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()
    tools = providers.DependenciesContainer()

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

    onboarding_repository = providers.Factory(
        OnboardingRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
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


class ApplicationContainer(containers.DeclarativeContainer):
    """Application root container, grouping domain containers."""

    wiring_config = containers.WiringConfiguration(modules=[__name__])
    config = providers.Configuration()

    core = providers.Container(CoreContainer)
    adapters = providers.Container(AdaptersContainer)

    tenants = providers.Container(TenantsContainer, core=core)
    flows = providers.Container(FlowsContainer, core=core, adapters=adapters)
    agents = providers.Container(AgentsContainer, core=core, adapters=adapters)
    tools = providers.Container(ToolsContainer, core=core, adapters=adapters)
    ai_policy = providers.Container(AIPolicyContainer, core=core, adapters=adapters)
    rag = providers.Container(RAGContainer, core=core, adapters=adapters)
    execution = providers.Container(
        ExecutionContainer, core=core, adapters=adapters, tools=tools
    )
    onboarding = providers.Container(OnboardingContainer, core=core)
    prompts = providers.Container(
        PromptsContainer, core=core, adapters=adapters, execution=execution
    )
