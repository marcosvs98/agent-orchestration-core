from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update

from infra.database import DatabaseConnection
from infra.database.models.governance.llm_pricing import LLMPricing as LLMPricingModel


class LLMPricingRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_active_pricing(
        self, *, provider: str, provider_model: str
    ) -> Optional[LLMPricingModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(LLMPricingModel).where(
                    LLMPricingModel.provider == provider,
                    LLMPricingModel.provider_model == provider_model,
                    LLMPricingModel.status == "ACTIVE",
                )
            )
            return result.scalar_one_or_none()

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
            result = await session.execute(
                select(LLMPricingModel)
                .where(
                    LLMPricingModel.provider == provider,
                    LLMPricingModel.provider_model == provider_model,
                    LLMPricingModel.status == status,
                )
                .with_for_update()
            )
            instance = result.scalar_one_or_none()
            if instance:
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
                await session.refresh(instance)
                return instance

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
            return instance
