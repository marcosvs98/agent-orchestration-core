from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from decimal import Decimal

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.llm_pricing import LLMPricing

from seeds.demo.ids import (
    LLM_PRICING_GPT4O_ID,
    LLM_PRICING_GPT41_MINI_ID,
    LLM_PRICING_GPT4O_MINI_ID,
    LLM_PRICING_SLM_LOCAL_ID,
    PRINCIPAL_SYSTEM,
)


async def seed_llm_pricing() -> None:
    async with get_db() as session:
        pricing_rows = [
            (
                LLM_PRICING_GPT4O_MINI_ID,
                "OPENAI",
                "gpt-4o-mini",
                Decimal("0.150"),
                Decimal("0.600"),
                "ACTIVE",
            ),
            (
                LLM_PRICING_GPT4O_ID,
                "OPENAI",
                "gpt-4o",
                Decimal("5.000"),
                Decimal("15.000"),
                "ACTIVE",
            ),
            (
                LLM_PRICING_GPT41_MINI_ID,
                "OPENAI",
                "gpt-4.1-mini",
                Decimal("0.150"),
                Decimal("0.600"),
                "ACTIVE",
            ),
            (
                LLM_PRICING_SLM_LOCAL_ID,
                "SLM_LOCAL",
                "qwen2.5-1.5b-instruct-q4_k_m",
                Decimal("0.000"),
                Decimal("0.000"),
                "ACTIVE",
            ),
        ]

        for (
            pricing_id,
            provider,
            provider_model,
            input_cost,
            output_cost,
            status,
        ) in pricing_rows:
            result = await session.execute(
                select(LLMPricing).where(LLMPricing.llm_pricing_id == pricing_id)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    LLMPricing(
                        llm_pricing_id=pricing_id,
                        provider=provider,
                        provider_model=provider_model,
                        unit="tokens",
                        input_cost_per_1k=input_cost,
                        output_cost_per_1k=output_cost,
                        currency="USD",
                        status=status,
                        created_by=PRINCIPAL_SYSTEM,
                    )
                )
            else:
                existing.provider = provider
                existing.provider_model = provider_model
                existing.unit = "tokens"
                existing.input_cost_per_1k = input_cost
                existing.output_cost_per_1k = output_cost
                existing.currency = "USD"
                existing.status = status
                existing.created_by = PRINCIPAL_SYSTEM
                session.add(existing)

        await session.commit()
