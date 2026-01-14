from domain.onboarding.ports.service import OnboardingServicePort
from exceptions.service_exceptions import NotImplementedServiceException


class OnboardingService(OnboardingServicePort):
    async def list_onboardings(self):
        raise NotImplementedServiceException()

    async def create_onboarding(self, onboarding_create):
        raise NotImplementedServiceException()

    async def create_onboarding_run(self, onboarding_run_create):
        raise NotImplementedServiceException()

    async def get_onboarding_run(self, onboarding_run_id: str):
        raise NotImplementedServiceException()

    async def list_onboarding_versions(self, onboarding_id: str):
        raise NotImplementedServiceException()
