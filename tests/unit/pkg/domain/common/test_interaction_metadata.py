from domain.common.interaction_metadata import (
    ACCEPTED_END_USER_AUTHORIZATION_METADATA_KEYS,
    END_USER_AUTHORIZATION_METADATA_KEY,
    LEGACY_END_USER_AUTHORIZATION_METADATA_KEYS,
    resolve_metadata_value,
)
from domain.conversation.utils.message_history import _FORBIDDEN_METADATA_KEYS
from domain.tools.services.tool_import_http_base import DEFAULT_IMPORT_TOOL_HEADERS


def test_the_canonical_key_carries_no_client_name() -> None:
    assert END_USER_AUTHORIZATION_METADATA_KEY == "end_user_authorization"
    assert "uora" not in END_USER_AUTHORIZATION_METADATA_KEY


def test_imported_tools_bind_the_key_producers_actually_write() -> None:
    binding = DEFAULT_IMPORT_TOOL_HEADERS["Authorization"]["interaction_metadata_key"]

    assert binding == END_USER_AUTHORIZATION_METADATA_KEY


def test_the_deny_list_is_a_superset_of_every_accepted_key() -> None:
    assert ACCEPTED_END_USER_AUTHORIZATION_METADATA_KEYS <= _FORBIDDEN_METADATA_KEYS


def test_the_canonical_key_resolves_directly() -> None:
    metadata = {END_USER_AUTHORIZATION_METADATA_KEY: "Bearer token"}

    assert resolve_metadata_value(metadata, END_USER_AUTHORIZATION_METADATA_KEY) == "Bearer token"


def test_a_legacy_tool_config_still_resolves_against_the_canonical_metadata() -> None:
    legacy_key = next(iter(LEGACY_END_USER_AUTHORIZATION_METADATA_KEYS))
    metadata = {END_USER_AUTHORIZATION_METADATA_KEY: "Bearer token"}

    assert resolve_metadata_value(metadata, legacy_key) == "Bearer token"


def test_a_canonical_tool_config_still_resolves_against_legacy_metadata() -> None:
    legacy_key = next(iter(LEGACY_END_USER_AUTHORIZATION_METADATA_KEYS))
    metadata = {legacy_key: "Bearer token"}

    assert resolve_metadata_value(metadata, END_USER_AUTHORIZATION_METADATA_KEY) == "Bearer token"


def test_unrelated_keys_never_fall_back_to_the_authorization_aliases() -> None:
    metadata = {END_USER_AUTHORIZATION_METADATA_KEY: "Bearer token"}

    assert resolve_metadata_value(metadata, "tenant_id") is None


def test_blank_values_are_treated_as_absent() -> None:
    assert (
        resolve_metadata_value(
            {END_USER_AUTHORIZATION_METADATA_KEY: "   "}, END_USER_AUTHORIZATION_METADATA_KEY
        )
        is None
    )


def test_missing_metadata_yields_none() -> None:
    assert resolve_metadata_value({}, END_USER_AUTHORIZATION_METADATA_KEY) is None
