from dependency_injector import containers, providers

import settings
from adapters.cache.redis_adapter import RedisAdapter
from adapters.secrets.env_secret_resolver import EnvSecretResolver
from infra.database import DatabaseConnection, async_session, engine

from domain.tenants.controllers.tenants_controller import TenantsController
from domain.tenants.services.tenants_service import TenantsService
from domain.flows.controllers.flows_controller import FlowsController
from domain.flows.services.flows_service import FlowsService
from domain.flows.repositories.flows_repository import FlowsRepository
from domain.agents.controllers.agents_controller import AgentsController
from domain.agents.services.agents_service import AgentsService
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.tools.controllers.tools_controller import ToolsController
from domain.tools.services.tools_service import ToolsService
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from domain.ai_policy.controllers.ai_controller import AIController
from domain.ai_policy.services.ai_service import AIService
from domain.rag.controllers.rag_controller import RagController
from domain.rag.services.rag_service import RagService
from domain.execution.controllers.execution_controller import ExecutionController
from domain.execution.controllers.execution_plane_controller import ExecutionPlaneController
from domain.execution.services.execution_service import ExecutionService
from domain.execution.services.state_machine import RunLifecycleStateMachine
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.adapters.idempotency_service import IdempotencyService
from services.execution_boundary import ExecutionBoundary
from infra.http_tool_executor import HttpToolExecutor
from domain.governance.repositories.access_policy_repository import AccessPolicyRepository
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.governance.services.execution_limit_service import ExecutionLimitService
from domain.governance.repositories.rate_limit_policy_repository import RateLimitPolicyRepository
from domain.governance.services.rate_limit_service import RateLimitService
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.onboarding.controllers.onboarding_controller import OnboardingController
from domain.onboarding.services.onboarding_service import OnboardingService


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


class TenantsContainer(containers.DeclarativeContainer):
    tenants_service = providers.Factory(TenantsService)
    tenants_controller = providers.Factory(
        TenantsController, service=tenants_service
    )


class FlowsContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()

    flows_repository = providers.Factory(
        FlowsRepository,
        database_connection=core.database_connection,
    )
    execution_limit_policy_repository = providers.Factory(
        ExecutionLimitPolicyRepository,
        database_connection=core.database_connection,
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

    agents_repository = providers.Factory(
        AgentsRepository,
        database_connection=core.database_connection,
    )
    authoring_event_repository = providers.Factory(
        AuthoringEventRepository,
        database_connection=core.database_connection,
    )
    agents_service = providers.Factory(
        AgentsService, repository=agents_repository, authoring_events=authoring_event_repository
    )
    agents_controller = providers.Factory(AgentsController, service=agents_service)


class ToolsContainer(containers.DeclarativeContainer):
    tools_service = providers.Factory(ToolsService)
    tools_controller = providers.Factory(ToolsController, service=tools_service)


class AIPolicyContainer(containers.DeclarativeContainer):
    ai_service = providers.Factory(AIService)
    ai_controller = providers.Factory(AIController, service=ai_service)


class RAGContainer(containers.DeclarativeContainer):
    rag_service = providers.Factory(RagService)
    rag_controller = providers.Factory(RagController, service=rag_service)


class ExecutionContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    adapters = providers.DependenciesContainer()

    access_policy_repository = providers.Factory(
        AccessPolicyRepository,
        database_connection=core.database_connection,
    )
    access_policy_service = providers.Factory(
        AccessPolicyService,
        repository=access_policy_repository,
    )
    rate_limit_policy_repository = providers.Factory(
        RateLimitPolicyRepository,
        database_connection=core.database_connection,
    )
    rate_limit_service = providers.Factory(
        RateLimitService,
        repository=rate_limit_policy_repository,
        redis_adapter=adapters.redis_adapter,
    )
    execution_limit_policy_repository = providers.Factory(
        ExecutionLimitPolicyRepository,
        database_connection=core.database_connection,
    )
    execution_repository = providers.Factory(
        ExecutionRepository,
        database_connection=core.database_connection,
    )
    idempotency_service = providers.Factory(
        IdempotencyService,
        redis_adapter=adapters.redis_adapter,
    )
    lifecycle = providers.Singleton(RunLifecycleStateMachine)
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
    )
    tool_executor = providers.Singleton(HttpToolExecutor)
    tool_orchestrator = providers.Factory(
        ToolOrchestrator,
        repository=execution_repository,
        executor=tool_executor,
        secret_resolver=adapters.secret_resolver,
    )
    execution_boundary = providers.Factory(
        ExecutionBoundary,
        execution_service=execution_service,
        tool_orchestrator=tool_orchestrator,
        access_policy_service=access_policy_service,
        rate_limit_service=rate_limit_service,
    )
    execution_controller = providers.Factory(ExecutionController, boundary=execution_boundary)
    execution_plane_controller = providers.Factory(
        ExecutionPlaneController, boundary=execution_boundary
    )


class OnboardingContainer(containers.DeclarativeContainer):
    onboarding_service = providers.Factory(OnboardingService)
    onboarding_controller = providers.Factory(
        OnboardingController, service=onboarding_service
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Application root container, grouping domain containers."""

    wiring_config = containers.WiringConfiguration(modules=[__name__])
    config = providers.Configuration()

    core = providers.Container(CoreContainer)
    adapters = providers.Container(AdaptersContainer)

    tenants = providers.Container(TenantsContainer)
    flows = providers.Container(FlowsContainer, core=core)
    agents = providers.Container(AgentsContainer, core=core)
    tools = providers.Container(ToolsContainer)
    ai_policy = providers.Container(AIPolicyContainer)
    rag = providers.Container(RAGContainer)
    execution = providers.Container(ExecutionContainer, core=core, adapters=adapters)
    onboarding = providers.Container(OnboardingContainer)
