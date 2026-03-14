from uuid import UUID

from domain.user_prompts.exceptions import UserPromptNotFoundException
from domain.user_prompts.ports.service import UserPromptsServicePort
from domain.user_prompts.repositories.user_prompts_repository import (
    UserPromptsRepository,
)
from domain.user_prompts.schemas.user_prompts import UserPrompt, UserPromptCreate


class UserPromptsService(UserPromptsServicePort):
    def __init__(self, repository: UserPromptsRepository) -> None:
        self.repository = repository

    async def list_user_prompts(self, *, tenant_id: UUID) -> list[UserPrompt]:
        items = await self.repository.list_active(tenant_id=tenant_id)
        return [
            UserPrompt(
                id=item.user_prompt_id,
                tenant_id=item.tenant_id,
                title=item.title,
                content=item.content,
                version=item.version,
                is_active=item.is_active,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]

    async def get_user_prompt(
        self, *, tenant_id: UUID, user_prompt_id: UUID
    ) -> UserPrompt:
        item = await self.repository.get_by_id(
            tenant_id=tenant_id,
            user_prompt_id=user_prompt_id,
        )
        if item is None:
            raise UserPromptNotFoundException()
        return UserPrompt(
            id=item.user_prompt_id,
            tenant_id=item.tenant_id,
            title=item.title,
            content=item.content,
            version=item.version,
            is_active=item.is_active,
            created_by=item.created_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def create_user_prompt(
        self, *, tenant_id: UUID, create: UserPromptCreate, principal_id: str
    ) -> UserPrompt:
        created = await self.repository.create(
            tenant_id=tenant_id,
            title=create.title,
            content=create.content,
            created_by=principal_id,
        )
        return UserPrompt(
            id=created.user_prompt_id,
            tenant_id=created.tenant_id,
            title=created.title,
            content=created.content,
            version=created.version,
            is_active=created.is_active,
            created_by=created.created_by,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def deactivate_user_prompt(
        self, *, tenant_id: UUID, user_prompt_id: UUID
    ) -> None:
        deactivated = await self.repository.deactivate(
            tenant_id=tenant_id,
            user_prompt_id=user_prompt_id,
        )
        if not deactivated:
            raise UserPromptNotFoundException()
