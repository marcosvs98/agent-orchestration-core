from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum, StrEnum
from ipaddress import IPv4Address, IPv6Address
from json import loads
from pathlib import PurePosixPath
from uuid import UUID

import pytest

from infra.database.json_serialization import jsonb_default, jsonb_serializer


class Priority(StrEnum):
    LOW = "low"


class Level(Enum):
    INFO = 20


def test_uuid_values_become_canonical_strings() -> None:
    value = UUID("00000000-0000-0000-0000-000000000700")

    assert loads(jsonb_serializer({"flow_id": value})) == {
        "flow_id": "00000000-0000-0000-0000-000000000700"
    }


def test_decimal_is_preserved_exactly_as_a_string_never_a_float() -> None:
    payload = loads(jsonb_serializer({"cost_usd": Decimal("0.000123")}))

    assert payload == {"cost_usd": "0.000123"}
    assert isinstance(payload["cost_usd"], str)


def test_decimal_keeps_precision_a_float_would_lose() -> None:
    exact = "0.12345678901234567890"

    assert loads(jsonb_serializer({"v": Decimal(exact)}))["v"] == exact


def test_plain_enums_serialize_to_their_value() -> None:
    assert jsonb_default(Level.INFO) == 20
    assert loads(jsonb_serializer({"level": Level.INFO})) == {"level": 20}


def test_string_enums_serialize_to_their_value_without_the_hook() -> None:
    assert loads(jsonb_serializer({"priority": Priority.LOW})) == {"priority": "low"}


def test_temporal_values_use_isoformat() -> None:
    moment = datetime(2026, 8, 18, 12, 30, tzinfo=UTC)

    payload = loads(jsonb_serializer({"at": moment, "d": date(2026, 8, 18), "t": time(1, 2)}))

    assert payload == {"at": "2026-08-18T12:30:00+00:00", "d": "2026-08-18", "t": "01:02:00"}


def test_addresses_and_paths_become_strings() -> None:
    payload = loads(
        jsonb_serializer(
            {"v4": IPv4Address("10.0.0.1"), "v6": IPv6Address("::1"), "p": PurePosixPath("/a/b")}
        )
    )

    assert payload == {"v4": "10.0.0.1", "v6": "::1", "p": "/a/b"}


def test_nested_payloads_are_converted_at_every_depth() -> None:
    value = UUID("11111111-1111-1111-1111-111111111111")

    payload = loads(jsonb_serializer({"a": [{"b": {"c": [value]}}]}))

    assert payload == {"a": [{"b": {"c": ["11111111-1111-1111-1111-111111111111"]}}]}


def test_json_native_values_are_untouched() -> None:
    original = {"s": "x", "i": 1, "f": 1.5, "b": True, "n": None, "l": [1, 2], "d": {"k": "v"}}

    assert loads(jsonb_serializer(original)) == original


@pytest.mark.parametrize("value", [{1, 2}, frozenset({1}), b"\xff\xfe", bytearray(b"\x00")])
def test_lossy_or_unordered_types_are_rejected_rather_than_silently_coerced(value: object) -> None:
    with pytest.raises(TypeError):
        jsonb_serializer({"v": value})


def test_non_finite_floats_are_rejected_instead_of_emitting_invalid_json() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            jsonb_serializer({"v": value})


def test_unknown_objects_still_raise_type_error() -> None:
    class Opaque:
        pass

    with pytest.raises(TypeError, match="Opaque"):
        jsonb_serializer({"v": Opaque()})


def test_non_string_mapping_keys_remain_unsupported() -> None:
    with pytest.raises(TypeError, match="keys must be"):
        jsonb_serializer({UUID("22222222-2222-2222-2222-222222222222"): 1})
