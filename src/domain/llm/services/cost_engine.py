from __future__ import annotations

from typing import Mapping

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.governance.repositories.llm_pricing_repository import LLMPricingRepository
from exceptions.service_exceptions import DomainValidationException


class CostEngine:
    def __init__(
        self, pricing_repository: LLMPricingRepository, tracer: RuntimeTracerPort
    ) -> None:
        self.pricing_repository = pricing_repository
        self.tracer = tracer

    @staticmethod
    def _tokens(value: Mapping[str, int] | None, key: str) -> int:
        if value is None:
            return 0
        token_val = value.get(key)
        if token_val is None:
            return 0
        try:
            return int(token_val)
        except (TypeError, ValueError):
            return 0

    async def compute_cost(
        self,
        *,
        provider: str,
        provider_model: str,
        token_usage: Mapping[str, int] | None,
    ) -> float:
        pricing = await self.pricing_repository.get_active_pricing(
            provider=provider, provider_model=provider_model
        )
        if pricing is None:
            raise DomainValidationException(message="llm_pricing_not_found")

        input_tokens = self._tokens(token_usage, "input_tokens")
        output_tokens = self._tokens(token_usage, "output_tokens")

        input_cost = (input_tokens / 1000) * float(pricing.input_cost_per_1k)
        output_cost = (output_tokens / 1000) * float(pricing.output_cost_per_1k)
        return round(input_cost + output_cost, 6)
