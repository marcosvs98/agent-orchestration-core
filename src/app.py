import sys
from fastapi import FastAPI
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from settings import APPLICATION_NAME, APPLICATION_VERSION, APPLICATION_DESCRIPTION
from adapters.observability.logging import get_logger, configure_logger
from rest import init_middlewares, init_routes
from containers import ApplicationContainer

configure_logger(is_async=False)

logger = get_logger()

logger.debug(
    "Python version",
    major=sys.version_info.major,
    minor=sys.version_info.minor,
    micro=sys.version_info.micro,
)


def create_app() -> FastAPI:
    container = ApplicationContainer()
    container.config.from_dict(
        {
            "application_name": APPLICATION_NAME,
        }
    )
    container.init_resources()
    container.wire(modules=[__name__])

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Service started")
        yield
        logger.info("Agent Router shutdown")
        try:
            tracer = container.adapters.tracer()
            if tracer:
                tracer.shutdown()
        except Exception as e:
            logger.error(
                "Failed to shutdown tracer", error=str(e), error_type=type(e).__name__
            )
        container.shutdown_resources()
        logger.debug("Service resources cleaned")

    app = FastAPI(
        title=APPLICATION_NAME,
        description=APPLICATION_DESCRIPTION,
        version=APPLICATION_VERSION,
        lifespan=lifespan,
    )

    app.state.container = container
    init_middlewares(app)

    init_routes(
        app,
        [
            container.tenants.tenants_controller(),
            container.flows.flows_controller(),
            container.agents.agents_controller(),
            container.tools.tools_controller(),
            container.ai_policy.ai_controller(),
            container.rag.rag_controller(),
            container.human_sla.human_sla_controller(),
            container.execution.execution_controller(),
            container.execution.execution_plane_controller(),
            container.conversation.conversation_controller(),
            container.onboarding.onboarding_controller(),
            container.prompts.prompt_controller(),
            container.user_prompts.user_prompts_controller(),
            container.governance.governance_policies_controller(),
            container.governance.llm_admin_controller(),
        ],
    )
    return app


app = create_app()
