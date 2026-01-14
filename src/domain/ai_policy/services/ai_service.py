from domain.ai_policy.ports.service import AIServicePort
from exceptions.service_exceptions import NotImplementedServiceException


class AIService(AIServicePort):
    async def list_ai_tasks(self):
        raise NotImplementedServiceException()

    async def create_ai_execution_policy(self, ai_execution_policy_create):
        raise NotImplementedServiceException()

    async def create_ai_execution_policy_version(self, ai_execution_policy_version_create):
        raise NotImplementedServiceException()

    async def list_models(self):
        raise NotImplementedServiceException()
