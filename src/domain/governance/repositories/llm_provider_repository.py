from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from infra.database import DatabaseConnection
from infra.database.models.governance.llm_provider_config import LLMProviderConfig as LLMProviderConfigModel


class LLMProviderRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_active_config(self, *, tenant_id: UUID, provider: str) -> Optional[LLMProviderConfigModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(LLMProviderConfigModel).where(
                    LLMProviderConfigModel.tenant_id == tenant_id,
                    LLMProviderConfigModel.provider == provider,
                    LLMProviderConfigModel.status == "ACTIVE",
                )
            )
            return result.scalar_one_or_none()

    async def upsert_config(
        self,
        *,
        tenant_id: UUID,
        provider: str,
        base_url: str | None,
        credential_secret_ref: str | None,
        status: str,
        created_by: str,
    ) -> LLMProviderConfigModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(LLMProviderConfigModel)
                .where(
                    LLMProviderConfigModel.tenant_id == tenant_id,
                    LLMProviderConfigModel.provider == provider,
                    LLMProviderConfigModel.status == status,
                )
                .with_for_update()
            )
            instance = result.scalar_one_or_none()
            if instance:
                await session.execute(
                    update(LLMProviderConfigModel)
                    .where(LLMProviderConfigModel.llm_provider_config_id == instance.llm_provider_config_id)
                    .values(
                        base_url=base_url,
                        credential_secret_ref=credential_secret_ref,
                        created_by=created_by,
                    )
                )
                await session.commit()
                await session.refresh(instance)
                return instance

            instance = LLMProviderConfigModel(
                tenant_id=tenant_id,
                provider=provider,
                status=status,
                base_url=base_url,
                credential_secret_ref=credential_secret_ref,
                created_by=created_by,
            )
            session.add(instance)
            await session.commit()
            return instance
