from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.llm.schemas.usage import LLMUsageRecord


def test_fractional_latency_is_rounded_to_whole_milliseconds() -> None:
    record = LLMUsageRecord(latency_ms=3193.1545430561528)

    assert record.latency_ms == 3193


def test_fractional_latency_rounds_up_past_the_halfway_point() -> None:
    assert LLMUsageRecord(latency_ms=12.7).latency_ms == 13


def test_integer_latency_is_preserved_exactly() -> None:
    assert LLMUsageRecord(latency_ms=250).latency_ms == 250


def test_absent_latency_stays_none() -> None:
    assert LLMUsageRecord().latency_ms is None
    assert LLMUsageRecord(latency_ms=None).latency_ms is None


@pytest.mark.parametrize("value", ["250", True, [250]])
def test_non_numeric_latency_is_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        LLMUsageRecord(latency_ms=value)


def test_the_record_stays_frozen_and_carries_cost_as_decimal() -> None:
    record = LLMUsageRecord(cost_usd=Decimal("0.0012"), latency_ms=1.4)

    assert record.cost_usd == Decimal("0.0012")
    assert record.latency_ms == 1
    with pytest.raises(ValidationError):
        record.latency_ms = 2
