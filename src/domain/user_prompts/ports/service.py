from abc import ABC, abstractmethod
from uuid import UUID

from domain.user_prompts.schemas.user_prompts import UserPrompt, UserPromptCreate
from exceptions.service_exceptions import NotImplementedServiceException


class UserPromptsServicePort(ABC):
    @abstractmethod
    async def list_user_prompts(self, *, tenant_id: UUID) -> list[UserPrompt]:
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_user_prompt(self, *, tenant_id: UUID, user_prompt_id: UUID) -> UserPrompt:
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_user_prompt(
        self, *, tenant_id: UUID, create: UserPromptCreate, principal_id: str
    ) -> UserPrompt:
        raise NotImplementedServiceException()

    @abstractmethod
    async def deactivate_user_prompt(self, *, tenant_id: UUID, user_prompt_id: UUID) -> None:
        raise NotImplementedServiceException()
