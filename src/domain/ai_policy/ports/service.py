from abc import ABC, abstractmethod
from exceptions.service_exceptions import NotImplementedServiceException


class AIServicePort(ABC):
    @abstractmethod
    async def create_ai_execution_policy(self, ai_execution_policy_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_ai_execution_policy_version(
        self, ai_execution_policy_version_create
    ):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_models(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_model(self, model_create):
        raise NotImplementedServiceException()
