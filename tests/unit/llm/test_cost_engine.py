import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from domain.llm.services.cost_engine import CostEngine


def _fake_tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


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
    engine = CostEngine(repo, tracer=_fake_tracer())
    cost = await engine.compute_cost(
        provider="OPENAI",
        provider_model="gpt-4o-mini",
        token_usage={"input_tokens": 1000, "output_tokens": 500},
    )
    # 1000 * 0.001 + 500 * 0.002 = 1 + 1 = 2 (in units of 0.001) => 0.002
    assert cost == 0.002


@pytest.mark.asyncio
async def test_compute_cost_raises_when_no_pricing():
    from exceptions.service_exceptions import DomainValidationException

    repo = MagicMock()
    repo.get_active_pricing = AsyncMock(return_value=None)
    engine = CostEngine(repo, tracer=_fake_tracer())
    with pytest.raises(DomainValidationException, match="llm_pricing_not_found"):
        await engine.compute_cost(
            provider="x",
            provider_model="y",
            token_usage={"input_tokens": 1, "output_tokens": 1},
        )


def test_tokens_helper():
    repo = MagicMock()
    engine = CostEngine(repo, tracer=_fake_tracer())
    assert CostEngine._tokens(None, "input_tokens") == 0
    assert CostEngine._tokens({}, "input_tokens") == 0
    assert CostEngine._tokens({"input_tokens": "10"}, "input_tokens") == 10
    assert CostEngine._tokens({"input_tokens": "bad"}, "input_tokens") == 0
