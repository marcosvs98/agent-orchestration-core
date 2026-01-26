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
    LLM_PRICING_GPT4O_MINI_ID,
    PRINCIPAL_SYSTEM,
)


async def seed_llm_pricing() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(LLMPricing).where(
                LLMPricing.llm_pricing_id == LLM_PRICING_GPT4O_MINI_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            pricing = LLMPricing(
                llm_pricing_id=LLM_PRICING_GPT4O_MINI_ID,
                provider="OPENAI",
                provider_model="gpt-4o-mini",
                unit="tokens",
                input_cost_per_1k=Decimal("0.150"),
                output_cost_per_1k=Decimal("0.600"),
                currency="USD",
                status="ACTIVE",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(pricing)
            await session.commit()
