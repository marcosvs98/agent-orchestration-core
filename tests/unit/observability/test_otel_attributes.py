from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4

import pytest
import structlog

from adapters.observability import otel_attributes as attrs


class Colour(str, Enum):
    RED = "red"


def test_none_is_dropped_rather_than_stringified() -> None:
    assert attrs.to_attribute_value(None) is None


def test_bool_stays_bool_and_is_not_collapsed_into_int() -> None:
    value = attrs.to_attribute_value(True)

    assert value is True
    assert isinstance(value, bool)


@pytest.mark.parametrize("raw", [0, 7, -3])
def test_int_passes_through_as_int(raw: int) -> None:
    converted = attrs.to_attribute_value(raw)

    assert converted == raw
    assert isinstance(converted, int)


def test_float_passes_through_as_float() -> None:
    converted = attrs.to_attribute_value(1.5)

    assert converted == 1.5
    assert isinstance(converted, float)


def test_uuid_becomes_its_string_form() -> None:
    identifier = uuid4()

    assert attrs.to_attribute_value(identifier) == str(identifier)


def test_decimal_becomes_float_so_it_can_be_aggregated() -> None:
    converted = attrs.to_attribute_value(Decimal("0.0012"))

    assert converted == pytest.approx(0.0012)
    assert isinstance(converted, float)


def test_enum_uses_its_value() -> None:
    assert attrs.to_attribute_value(Colour.RED) == "red"


def test_datetime_and_date_use_isoformat() -> None:
    moment = datetime(2026, 8, 17, 1, 2, 3, tzinfo=timezone.utc)

    assert attrs.to_attribute_value(moment) == moment.isoformat()
    assert attrs.to_attribute_value(date(2026, 8, 17)) == "2026-08-17"


def test_arbitrary_object_falls_back_to_str() -> None:
    class Opaque:
        def __str__(self) -> str:
            return "opaque-thing"

    assert attrs.to_attribute_value(Opaque()) == "opaque-thing"


def test_mapping_becomes_a_json_string() -> None:
    converted = attrs.to_attribute_value({"a": 1})

    assert isinstance(converted, str)
    assert '"a"' in converted


def test_homogeneous_sequences_become_tuples() -> None:
    assert attrs.to_attribute_value(["a", "b"]) == ("a", "b")
    assert attrs.to_attribute_value([1, 2]) == (1, 2)
    assert attrs.to_attribute_value([1.5, 2.5]) == (1.5, 2.5)
    assert attrs.to_attribute_value([True, False]) == (True, False)


def test_mixed_sequence_becomes_a_json_string() -> None:
    converted = attrs.to_attribute_value(["a", 1])

    assert isinstance(converted, str)
    assert converted.startswith("[")


def test_empty_sequence_is_dropped() -> None:
    assert attrs.to_attribute_value([]) is None


def test_set_is_accepted_as_a_sequence() -> None:
    converted = attrs.to_attribute_value({"only"})

    assert converted == ("only",)


def test_truncate_respects_the_configured_maximum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attrs, "OTEL_ATTRIBUTE_MAX_LENGTH", 10)

    truncated = attrs.truncate("x" * 50)

    assert len(truncated) == 10
    assert truncated.endswith("...")


def test_truncate_leaves_short_values_alone() -> None:
    assert attrs.truncate("short") == "short"


def test_long_strings_inside_sequences_are_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attrs, "OTEL_ATTRIBUTE_MAX_LENGTH", 8)

    converted = attrs.to_attribute_value(["y" * 40])

    assert converted == ("yyyyy...",)


def test_json_attribute_handles_unserialisable_values() -> None:
    encoded = attrs.json_attribute({"when": datetime(2026, 1, 1)})

    assert isinstance(encoded, str)
    assert "2026" in encoded


def test_json_attribute_returns_none_for_none() -> None:
    assert attrs.json_attribute(None) is None


def test_sanitize_attributes_drops_none_values_and_bad_keys() -> None:
    sanitized = attrs.sanitize_attributes({"kept": 1, "dropped": None, "": 2, 5: 3})

    assert sanitized == {"kept": 1}


def test_sanitize_attributes_returns_empty_for_falsy_source() -> None:
    assert attrs.sanitize_attributes(None) == {}
    assert attrs.sanitize_attributes({}) == {}


def test_context_attributes_keeps_only_allowlisted_keys() -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id="c-1",
        tenant_id="t-1",
        **{"request.url.path": "/v1/flows"},
    )
    try:
        allowed = attrs.context_attributes()
    finally:
        structlog.contextvars.clear_contextvars()

    assert allowed == {
        "correlation_id": "c-1",
        "tenant_id": "t-1",
        "request.url.path": "/v1/flows",
    }


def test_context_attributes_never_leaks_query_string_secrets() -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        **{
            "request.url": "http://h/v1/flows/runs?api_key=SECRET&q=hi",
            "request.query_params": {"api_key": "SECRET"},
            "request.headers": {"authorization": "Bearer SECRET"},
            "request.user_agent": "curl",
            "request.referer": "http://elsewhere",
            "correlation_id": "c-1",
        }
    )
    try:
        allowed = attrs.context_attributes()
    finally:
        structlog.contextvars.clear_contextvars()

    assert "SECRET" not in repr(allowed)
    assert set(allowed) == {"correlation_id"}


def test_context_attributes_survives_a_broken_contextvar_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode() -> dict:
        raise RuntimeError("no contextvars")

    monkeypatch.setattr(structlog.contextvars, "get_contextvars", explode)

    assert attrs.context_attributes() == {}


def test_usage_attributes_map_openai_and_neutral_token_names() -> None:
    assert attrs.usage_attributes(
        {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    ) == {
        attrs.GEN_AI_USAGE_INPUT_TOKENS: 10,
        attrs.GEN_AI_USAGE_OUTPUT_TOKENS: 20,
        attrs.GEN_AI_USAGE_TOTAL_TOKENS: 30,
    }
    assert attrs.usage_attributes({"input_tokens": 5, "output_tokens": 6}) == {
        attrs.GEN_AI_USAGE_INPUT_TOKENS: 5,
        attrs.GEN_AI_USAGE_OUTPUT_TOKENS: 6,
    }


def test_usage_attributes_are_integers_not_strings() -> None:
    usage = attrs.usage_attributes({"prompt_tokens": "10", "cached_input_tokens": 4})

    assert usage[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert isinstance(usage[attrs.GEN_AI_USAGE_INPUT_TOKENS], int)
    assert usage[attrs.GEN_AI_USAGE_CACHED_INPUT_TOKENS] == 4


def test_usage_attributes_coerce_floats_and_reject_bools() -> None:
    assert attrs.usage_attributes({"prompt_tokens": 12.9})[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 12
    assert attrs.usage_attributes({"prompt_tokens": True}) == {}


def test_usage_attributes_ignore_non_mappings_and_unparseable_strings() -> None:
    assert attrs.usage_attributes(None) == {}
    assert attrs.usage_attributes("not a mapping") == {}
    assert attrs.usage_attributes({"prompt_tokens": "many"}) == {}


def test_cost_attributes_produce_a_float_not_a_json_string() -> None:
    cost = attrs.cost_attributes({"total_cost": Decimal("0.0012")})

    assert cost == {attrs.GEN_AI_COST_USD: pytest.approx(0.0012)}
    assert isinstance(cost[attrs.GEN_AI_COST_USD], float)


def test_cost_attributes_accept_alternative_key_names() -> None:
    assert attrs.cost_attributes({"cost_usd": "0.5"})[attrs.GEN_AI_COST_USD] == 0.5
    assert attrs.cost_attributes({"total_cost_usd": 2})[attrs.GEN_AI_COST_USD] == 2.0


def test_cost_attributes_ignore_unusable_input() -> None:
    assert attrs.cost_attributes(None) == {}
    assert attrs.cost_attributes({"total_cost": "free"}) == {}
    assert attrs.cost_attributes({"unrelated": 1}) == {}
    assert attrs.cost_attributes({"total_cost": True}) == {}


def test_model_parameters_are_mapped_to_gen_ai_names_and_unknowns_dropped() -> None:
    mapped = attrs.model_parameter_attributes(
        {"temperature": 0.2, "max_tokens": 2048, "nonsense": 1, "stop": None}
    )

    assert mapped == {
        "gen_ai.request.temperature": 0.2,
        "gen_ai.request.max_tokens": 2048,
    }


def test_model_parameters_ignore_non_mappings() -> None:
    assert attrs.model_parameter_attributes(None) == {}
    assert attrs.model_parameter_attributes([1, 2]) == {}
