from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class OnboardingServicePort(ABC):
    @abstractmethod
    async def list_onboardings(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_onboarding(self, onboarding_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_onboarding_run(self, onboarding_run_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_onboarding_run(self, onboarding_run_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_onboarding_versions(self, onboarding_id: str):
        raise NotImplementedServiceException()
