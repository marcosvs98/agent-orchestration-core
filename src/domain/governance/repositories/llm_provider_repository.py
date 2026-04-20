from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
from infra.database import DatabaseConnection
from infra.database.models.governance.llm_provider_config import (
    LLMProviderConfig as LLMProviderConfigModel,
)


class LLMProviderRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_active_config(
        self, *, tenant_id: UUID, provider: str
    ) -> Optional[LLMProviderConfigModel]:
        key = f"llm_provider_config:{tenant_id}:{provider}"
        if self.cache_adapter:
            cached = await self.cache_adapter.get(key)
            if cached:
                return LLMProviderConfigModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(LLMProviderConfigModel).where(
                LLMProviderConfigModel.tenant_id == tenant_id,
                LLMProviderConfigModel.provider == provider,
                LLMProviderConfigModel.status == "ACTIVE",
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_provider_repository.get_active_config",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "provider": provider,
                    },
                },
                metadata={"retriever_name": "get_active_config"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                config = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if config else 0,
                            "found": config is not None,
                        }
                    )

                if self.cache_adapter and config:
                    await self.cache_adapter.set(key, config.to_dict(), ttl=60)
                return config

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
            stmt = (
                select(LLMProviderConfigModel)
                .where(
                    LLMProviderConfigModel.tenant_id == tenant_id,
                    LLMProviderConfigModel.provider == provider,
                    LLMProviderConfigModel.status == status,
                )
                .with_for_update()
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_provider_repository.get_existing_config",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "provider": provider,
                        "status": status,
                    },
                },
                metadata={"retriever_name": "get_existing_config"},
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
                    name="domain.governance.llm_provider_repository.update_config",
                    input={
                        "llm_provider_config_id": str(instance.llm_provider_config_id),
                    },
                ):
                    await session.execute(
                        update(LLMProviderConfigModel)
                        .where(
                            LLMProviderConfigModel.llm_provider_config_id
                            == instance.llm_provider_config_id
                        )
                        .values(
                            base_url=base_url,
                            credential_secret_ref=credential_secret_ref,
                            created_by=created_by,
                        )
                    )
                    await session.commit()
                    if self.cache_adapter:
                        await self.cache_adapter.delete(
                            f"llm_provider_config:{tenant_id}:{provider}"
                        )
                    await session.refresh(instance)
                    return instance

            with self.tracer.observe(
                as_type="tool",
                name="domain.governance.llm_provider_repository.create_config",
                input={"tenant_id": str(tenant_id), "provider": provider},
            ):
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
                if self.cache_adapter:
                    await self.cache_adapter.delete(f"llm_provider_config:{tenant_id}:{provider}")
                return instance
