from __future__ import annotations

import pytest

from domain.execution.repositories import execution_repository as er
from exceptions.service_exceptions import DomainValidationException


def test_preferences_dict_from_profile_extracts_values() -> None:
    profile = {
        "memory_preferences": {
            "a": {"value": 1},
            "b": "raw",
        }
    }
    out = er._preferences_dict_from_profile(profile)
    assert out["a"] == 1
    assert out["b"] == "raw"


def test_preferences_dict_from_profile_invalid_returns_empty() -> None:
    assert er._preferences_dict_from_profile({"memory_preferences": "nope"}) == {}


def test_validate_profile_schema_version_accepts_none() -> None:
    er._validate_profile_schema_version({})


def test_validate_profile_schema_version_invalid_int() -> None:
    with pytest.raises(DomainValidationException, match="user_memory_profile_schema_invalid"):
        er._validate_profile_schema_version({"profile_schema_version": "x"})


def test_validate_profile_schema_version_out_of_range() -> None:
    with pytest.raises(DomainValidationException, match="user_memory_profile_schema_unsupported"):
        er._validate_profile_schema_version({"profile_schema_version": 99})
