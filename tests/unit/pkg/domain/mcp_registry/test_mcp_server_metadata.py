from __future__ import annotations

import pytest

from domain.mcp_registry.mcp_server_metadata import (
    OUTBOUND_AUTHORIZATION_SECRET_REF_KEY,
    outbound_authorization_secret_ref_from_server_metadata,
)


class TestOutboundAuthorizationSecretRefFromServerMetadata:
    def test_returns_none_when_meta_is_not_dict(self):
        assert outbound_authorization_secret_ref_from_server_metadata("string") is None
        assert outbound_authorization_secret_ref_from_server_metadata(42) is None
        assert outbound_authorization_secret_ref_from_server_metadata(None) is None
        assert outbound_authorization_secret_ref_from_server_metadata([]) is None

    def test_returns_none_when_key_absent(self):
        assert outbound_authorization_secret_ref_from_server_metadata({}) is None
        assert outbound_authorization_secret_ref_from_server_metadata({"other_key": "value"}) is None

    def test_returns_none_when_key_is_none(self):
        assert outbound_authorization_secret_ref_from_server_metadata({OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: None}) is None

    def test_returns_none_when_value_is_blank(self):
        assert outbound_authorization_secret_ref_from_server_metadata({OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: "   "}) is None
        assert outbound_authorization_secret_ref_from_server_metadata({OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: ""}) is None

    def test_returns_stripped_string_when_present(self):
        result = outbound_authorization_secret_ref_from_server_metadata(
            {OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: "  env:MY_SECRET  "}
        )
        assert result == "env:MY_SECRET"

    def test_returns_string_as_is_when_no_padding(self):
        result = outbound_authorization_secret_ref_from_server_metadata(
            {OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: "env:MY_SECRET"}
        )
        assert result == "env:MY_SECRET"

    def test_coerces_non_string_value_to_str(self):
        result = outbound_authorization_secret_ref_from_server_metadata(
            {OUTBOUND_AUTHORIZATION_SECRET_REF_KEY: 123}
        )
        assert result == "123"
