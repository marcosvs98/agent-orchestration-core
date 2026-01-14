import uuid

import pytest

from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.llm.services.cost_engine import CostEngine


class _PricingRepo(LLMPricingRepository):
    def __init__(self) -> None:  # type: ignore[call-arg]
        self.record = None

    async def get_active_pricing(self, *, provider: str, provider_model: str):
        return type(
            "Pricing",
            (),
            {
                "provider": provider,
                "provider_model": provider_model,
                "input_cost_per_1k": 0.001,
                "output_cost_per_1k": 0.002,
            },
        )()


@pytest.mark.asyncio
async def test_cost_engine_computes_cost():
    repo = _PricingRepo()
    engine = CostEngine(repo)
    cost = await engine.compute_cost(
        provider="OPENAI",
        provider_model="gpt-4o-mini",
        token_usage={"input_tokens": 1000, "output_tokens": 500},
    )
    # 1000 * 0.001 + 500 * 0.002 = 1 + 1 = 2 (in units of 0.001) => 0.002
    assert cost == 0.002
