from fastapi import APIRouter, Depends, status

from domain.onboarding.schemas.onboarding import (
    Onboarding,
    OnboardingCreate,
    OnboardingRun,
    OnboardingRunCreate,
    OnboardingVersion,
)
from domain.onboarding.services.onboarding_service import OnboardingService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import NotImplementedServiceException
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
        r("/onboardings", self.list_onboardings, methods=["GET"], response_model=list[Onboarding], responses=self._resp501())
        r("/onboardings", self.create_onboarding, methods=["POST"], response_model=Onboarding, status_code=status.HTTP_201_CREATED, responses=self._resp501())
        r("/onboarding-runs", self.create_onboarding_run, methods=["POST"], response_model=OnboardingRun, status_code=status.HTTP_201_CREATED, responses=self._resp501())
        r("/onboarding-runs/{onboarding_run_id}", self.get_onboarding_run, methods=["GET"], response_model=OnboardingRun, responses=self._resp501())
        r("/onboardings/{onboarding_id}/versions", self.list_onboarding_versions, methods=["GET"], response_model=list[OnboardingVersion], responses=self._resp501())

    def _resp501(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_501_NOT_IMPLEMENTED: {"model": ErrorResponse}}

    async def list_onboardings(self, _: AuthContext = Depends(get_auth_context)) -> list[Onboarding]:
        raise NotImplementedServiceException()

    async def create_onboarding(
        self,
        __: OnboardingCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> Onboarding:
        raise NotImplementedServiceException()

    async def create_onboarding_run(
        self,
        __: OnboardingRunCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> OnboardingRun:
        raise NotImplementedServiceException()

    async def get_onboarding_run(
        self, onboarding_run_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> OnboardingRun:
        raise NotImplementedServiceException()

    async def list_onboarding_versions(
        self,
        onboarding_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[OnboardingVersion]:
        raise NotImplementedServiceException()
