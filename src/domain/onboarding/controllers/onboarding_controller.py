from fastapi import APIRouter, Depends, Query, status

from domain.onboarding.schemas.onboarding import (
    Onboarding,
    OnboardingCreate,
    OnboardingRun,
    OnboardingRunCreate,
    OnboardingVersion,
    StepRun,
    StepRunAdvance,
)
from domain.onboarding.services.onboarding_service import OnboardingService
from domain.common.schemas.error import ErrorResponse
from utils.auth import AuthContext, get_auth_context


class OnboardingController:
    """HTTP controller for onboarding resources."""

    def __init__(self, service: OnboardingService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["onboarding"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/onboardings",
            self.list_onboardings,
            methods=["GET"],
            response_model=list[Onboarding],
        )
        r(
            "/onboardings",
            self.create_onboarding,
            methods=["POST"],
            response_model=Onboarding,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/onboarding-runs",
            self.create_onboarding_run,
            methods=["POST"],
            response_model=OnboardingRun,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/onboarding-runs/{onboarding_run_id}",
            self.get_onboarding_run,
            methods=["GET"],
            response_model=OnboardingRun,
        )
        r(
            "/onboardings/{onboarding_id}/versions",
            self.list_onboarding_versions,
            methods=["GET"],
            response_model=list[OnboardingVersion],
        )
        r(
            "/onboarding-runs/{onboarding_run_id}/steps",
            self.list_steps,
            methods=["GET"],
            response_model=list[StepRun],
        )
        r(
            "/onboarding-runs/{onboarding_run_id}/steps/{step_run_id}/advance",
            self.advance_step,
            methods=["POST"],
            response_model=StepRun,
        )

    def _resp501(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_501_NOT_IMPLEMENTED: {"model": ErrorResponse}}

    async def list_onboardings(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[Onboarding]:
        return await self.service.list_onboardings(tenant_id=auth.tenant_id, limit=limit)

    async def create_onboarding(
        self,
        onboarding_create: OnboardingCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> Onboarding:
        return await self.service.create_onboarding(
            tenant_id=auth.tenant_id,
            onboarding_create=onboarding_create,
            principal_id=auth.principal_id,
        )

    async def create_onboarding_run(
        self,
        onboarding_run_create: OnboardingRunCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> OnboardingRun:
        return await self.service.create_onboarding_run(
            tenant_id=auth.tenant_id,
            onboarding_run_create=onboarding_run_create,
            principal_id=auth.principal_id,
        )

    async def get_onboarding_run(
        self,
        onboarding_run_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> OnboardingRun:
        return await self.service.get_onboarding_run(
            tenant_id=auth.tenant_id, onboarding_run_id=onboarding_run_id
        )

    async def list_onboarding_versions(
        self,
        onboarding_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[OnboardingVersion]:
        return await self.service.list_onboarding_versions(
            tenant_id=auth.tenant_id, onboarding_id=onboarding_id
        )

    async def list_steps(
        self,
        onboarding_run_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[StepRun]:
        return await self.service.list_steps(
            tenant_id=auth.tenant_id, onboarding_run_id=onboarding_run_id
        )

    async def advance_step(
        self,
        onboarding_run_id: str,
        step_run_id: str,
        step_run_advance: StepRunAdvance,
        auth: AuthContext = Depends(get_auth_context),
    ) -> StepRun:
        return await self.service.advance_step(
            tenant_id=auth.tenant_id,
            onboarding_run_id=onboarding_run_id,
            step_run_id=step_run_id,
            input_payload=step_run_advance.input_payload,
            principal_id=auth.principal_id,
        )
