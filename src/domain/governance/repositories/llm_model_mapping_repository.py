from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.governance.llm_model_mapping import (
    LLMModelMapping as LLMModelMappingModel,
)


class LLMModelMappingRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_active_mapping(
        self, *, tenant_id: UUID, provider: str, model_alias: str
    ) -> Optional[LLMModelMappingModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.llm_model_mapping_repository.get_active_mapping",
            input={
                "tenant_id": str(tenant_id),
                "provider": provider,
                "model_alias": model_alias,
            },
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(LLMModelMappingModel).where(
                        LLMModelMappingModel.tenant_id == tenant_id,
                        LLMModelMappingModel.provider == provider,
                        LLMModelMappingModel.model_alias == model_alias,
                        LLMModelMappingModel.status == "ACTIVE",
                    )
                )
                return result.scalar_one_or_none()

    async def upsert_mapping(
        self,
        *,
        tenant_id: UUID,
        provider: str,
        model_alias: str,
        provider_model: str,
        status: str,
        created_by: str,
    ) -> LLMModelMappingModel:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_model_mapping_repository.get_existing_mapping",
                input={
                    "tenant_id": str(tenant_id),
                    "provider": provider,
                    "model_alias": model_alias,
                },
            ):
                result = await session.execute(
                    select(LLMModelMappingModel)
                    .where(
                        LLMModelMappingModel.tenant_id == tenant_id,
                        LLMModelMappingModel.provider == provider,
                        LLMModelMappingModel.model_alias == model_alias,
                        LLMModelMappingModel.status == status,
                    )
                    .with_for_update()
                )
                instance = result.scalar_one_or_none()
            if instance:
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.governance.llm_model_mapping_repository.update_mapping",
                    input={
                        "llm_model_mapping_id": str(instance.llm_model_mapping_id),
                    },
                ):
                    await session.execute(
                        update(LLMModelMappingModel)
                        .where(
                            LLMModelMappingModel.llm_model_mapping_id
                            == instance.llm_model_mapping_id
                        )
                        .values(provider_model=provider_model, created_by=created_by)
                    )
                    await session.commit()
                    await session.refresh(instance)
                    return instance

            with self.tracer.observe(
                as_type="tool",
                name="domain.governance.llm_model_mapping_repository.create_mapping",
                input={
                    "tenant_id": str(tenant_id),
                    "provider": provider,
                    "model_alias": model_alias,
                },
            ):
                instance = LLMModelMappingModel(
                    tenant_id=tenant_id,
                    provider=provider,
                    model_alias=model_alias,
                    provider_model=provider_model,
                    status=status,
                    created_by=created_by,
                )
                session.add(instance)
                await session.commit()
                return instance
