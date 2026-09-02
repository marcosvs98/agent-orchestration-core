from uuid import UUID

import pytest

from domain.rag.utils.rag_snapshot_hash import (
    normalize_json_for_rag_hash,
    rag_materialization_canonical_string,
    rag_materialization_sha256,
)


class DriverUUID(UUID):
    __slots__ = ()


RAG_CONFIG_ID = UUID("11111111-1111-1111-1111-111111111111")
CHUNKING_RULE_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_normalize_converts_uuid_to_lowercase_string():
    assert normalize_json_for_rag_hash(RAG_CONFIG_ID) == str(RAG_CONFIG_ID)


def test_normalize_converts_uuid_subclasses_returned_by_the_database_driver():
    driver_value = DriverUUID(str(CHUNKING_RULE_ID))

    assert normalize_json_for_rag_hash(driver_value) == str(CHUNKING_RULE_ID)


def test_normalize_converts_nested_uuid_subclasses():
    payload = {"ids": [DriverUUID(str(RAG_CONFIG_ID))], "nested": {"id": RAG_CONFIG_ID}}

    normalized = normalize_json_for_rag_hash(payload)

    assert normalized == {"ids": [str(RAG_CONFIG_ID)], "nested": {"id": str(RAG_CONFIG_ID)}}


def test_canonical_string_is_json_serializable_for_driver_uuids():
    canonical = rag_materialization_canonical_string(
        rag_config_id=DriverUUID(str(RAG_CONFIG_ID)),
        chunking_rule_id=DriverUUID(str(CHUNKING_RULE_ID)),
        params={"target_tokens": 500},
        policy_definition={"top_k_cap": 5},
    )

    assert str(RAG_CONFIG_ID) in canonical
    assert str(CHUNKING_RULE_ID) in canonical


def test_hash_is_stable_across_uuid_and_driver_uuid():
    plain = rag_materialization_sha256(
        rag_config_id=RAG_CONFIG_ID,
        chunking_rule_id=CHUNKING_RULE_ID,
        params={},
        policy_definition={},
    )
    driver = rag_materialization_sha256(
        rag_config_id=DriverUUID(str(RAG_CONFIG_ID)),
        chunking_rule_id=DriverUUID(str(CHUNKING_RULE_ID)),
        params={},
        policy_definition={},
    )

    assert plain == driver


def test_hash_changes_when_params_change():
    first = rag_materialization_sha256(
        rag_config_id=RAG_CONFIG_ID,
        chunking_rule_id=CHUNKING_RULE_ID,
        params={"target_tokens": 500},
        policy_definition={},
    )
    second = rag_materialization_sha256(
        rag_config_id=RAG_CONFIG_ID,
        chunking_rule_id=CHUNKING_RULE_ID,
        params={"target_tokens": 800},
        policy_definition={},
    )

    assert first != second


def test_canonical_string_orders_keys_deterministically():
    forward = rag_materialization_canonical_string(
        rag_config_id=RAG_CONFIG_ID,
        chunking_rule_id=CHUNKING_RULE_ID,
        params={"b": 2, "a": 1},
        policy_definition={},
    )
    reversed_input = rag_materialization_canonical_string(
        rag_config_id=RAG_CONFIG_ID,
        chunking_rule_id=CHUNKING_RULE_ID,
        params={"a": 1, "b": 2},
        policy_definition={},
    )

    assert forward == reversed_input


@pytest.mark.parametrize("value", [None, True, 1, 1.5, "text", [], {}])
def test_normalize_passes_through_json_native_values(value):
    assert normalize_json_for_rag_hash(value) == value
