from __future__ import annotations

from typing import Optional

from sqlalchemy import desc, select, update

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
from infra.database import DatabaseConnection
from infra.database.models.governance.llm_pricing import LLMPricing as LLMPricingModel


class LLMPricingRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_active_pricing(
        self, *, provider: str, provider_model: str
    ) -> Optional[LLMPricingModel]:
        key = f"llm_pricing:{provider}:{provider_model}"
        if self.cache_adapter:
            cached = await self.cache_adapter.get(key)
            if cached:
                return LLMPricingModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = (
                select(LLMPricingModel)
                .where(
                    LLMPricingModel.provider == provider,
                    LLMPricingModel.provider_model == provider_model,
                    LLMPricingModel.status == "ACTIVE",
                )
                .order_by(desc(LLMPricingModel.created_at))
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_pricing_repository.get_active_pricing",
                input={
                    "query": query_sql,
                    "params": {
                        "provider": provider,
                        "provider_model": provider_model,
                    },
                },
                metadata={"retriever_name": "get_active_pricing"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                pricing = result.scalars().first()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if pricing else 0,
                            "found": pricing is not None,
                        }
                    )

                if self.cache_adapter and pricing:
                    await self.cache_adapter.set(key, pricing.to_dict(), ttl=60)
                return pricing

    async def upsert_pricing(
        self,
        *,
        provider: str,
        provider_model: str,
        unit: str,
        input_cost_per_1k,
        output_cost_per_1k,
        currency: str,
        status: str,
        created_by: str,
    ) -> LLMPricingModel:
        async with self.db.get_session() as session:
            stmt = (
                select(LLMPricingModel)
                .where(
                    LLMPricingModel.provider == provider,
                    LLMPricingModel.provider_model == provider_model,
                    LLMPricingModel.status == status,
                )
                .order_by(desc(LLMPricingModel.created_at))
                .with_for_update()
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.llm_pricing_repository.get_existing_pricing",
                input={
                    "query": query_sql,
                    "params": {
                        "provider": provider,
                        "provider_model": provider_model,
                        "status": status,
                    },
                },
                metadata={"retriever_name": "get_existing_pricing"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                instance = result.scalars().first()

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
                    name="domain.governance.llm_pricing_repository.update_pricing",
                    input={"llm_pricing_id": str(instance.llm_pricing_id)},
                ):
                    await session.execute(
                        update(LLMPricingModel)
                        .where(LLMPricingModel.llm_pricing_id == instance.llm_pricing_id)
                        .values(
                            unit=unit,
                            input_cost_per_1k=input_cost_per_1k,
                            output_cost_per_1k=output_cost_per_1k,
                            currency=currency,
                            created_by=created_by,
                        )
                    )
                    await session.commit()
                    if self.cache_adapter:
                        await self.cache_adapter.delete(f"llm_pricing:{provider}:{provider_model}")
                    await session.refresh(instance)
                    return instance

            with self.tracer.observe(
                as_type="tool",
                name="domain.governance.llm_pricing_repository.create_pricing",
                input={"provider": provider, "provider_model": provider_model},
            ):
                instance = LLMPricingModel(
                    provider=provider,
                    provider_model=provider_model,
                    unit=unit,
                    input_cost_per_1k=input_cost_per_1k,
                    output_cost_per_1k=output_cost_per_1k,
                    currency=currency,
                    status=status,
                    created_by=created_by,
                )
                session.add(instance)
                await session.commit()
                if self.cache_adapter:
                    await self.cache_adapter.delete(f"llm_pricing:{provider}:{provider_model}")
                return instance
