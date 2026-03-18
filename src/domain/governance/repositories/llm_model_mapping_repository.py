from __future__ import annotations

from enum import StrEnum
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.governance.llm_model_mapping import (
    LLMModelMapping as LLMModelMappingModel,
)
from utils.query_compiler import compile_query


class LLMModelMappingStatus(StrEnum):
    ACTIVE = "ACTIVE"


class LLMModelMappingRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_active_mapping(
        self, *, tenant_id: UUID, provider: str, model_alias: str
    ) -> Optional[LLMModelMappingModel]:
        key = f"llm_mapping:{tenant_id}:{provider}:{model_alias}"
        if self.cache_adapter:
            cached = await self.cache_adapter.get(key)
            if cached:
                return LLMModelMappingModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = (
                select(LLMModelMappingModel)
                .where(
                    LLMModelMappingModel.tenant_id == tenant_id,
                    LLMModelMappingModel.provider == provider,
                    LLMModelMappingModel.model_alias == model_alias,
                    LLMModelMappingModel.status == LLMModelMappingStatus.ACTIVE.value,
                )
                .order_by(
                    LLMModelMappingModel.created_at.desc(),
                    LLMModelMappingModel.llm_model_mapping_id.desc(),
                )
                .limit(1)
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_model_mapping_repository.get_active_mapping",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "provider": provider,
                        "model_alias": model_alias,
                    },
                },
                metadata={"retriever_name": "get_active_mapping"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                mapping = result.scalars().first()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if mapping else 0,
                            "found": mapping is not None,
                        }
                    )

                if self.cache_adapter and mapping:
                    await self.cache_adapter.set(key, mapping.to_dict(), ttl=60)
                return mapping

    async def upsert_mapping(
        self,
        *,
        tenant_id: UUID,
        model_id: UUID,
        provider: str,
        model_alias: str,
        provider_model: str,
        status: str,
        created_by: str,
    ) -> LLMModelMappingModel:
        async with self.db.get_session() as session:
            stmt = (
                select(LLMModelMappingModel)
                .where(
                    LLMModelMappingModel.tenant_id == tenant_id,
                    LLMModelMappingModel.provider == provider,
                    LLMModelMappingModel.model_alias == model_alias,
                    LLMModelMappingModel.status == status,
                )
                .with_for_update()
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_model_mapping_repository.get_existing_mapping",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "provider": provider,
                        "model_alias": model_alias,
                        "status": status,
                    },
                },
                metadata={"retriever_name": "get_existing_mapping"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

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
                        .values(
                            model_id=model_id,
                            provider_model=provider_model,
                            created_by=created_by,
                        )
                    )
                    await session.commit()
                    if self.cache_adapter:
                        await self.cache_adapter.delete(
                            f"llm_mapping:{tenant_id}:{provider}:{model_alias}"
                        )
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
                    model_id=model_id,
                    provider=provider,
                    model_alias=model_alias,
                    provider_model=provider_model,
                    status=status,
                    created_by=created_by,
                )
                session.add(instance)
                await session.commit()
                if self.cache_adapter:
                    await self.cache_adapter.delete(
                        f"llm_mapping:{tenant_id}:{provider}:{model_alias}"
                    )
                return instance
