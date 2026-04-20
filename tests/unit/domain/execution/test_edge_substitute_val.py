"""SubstituteVal.resolve branches (edge_evaluator)."""

from __future__ import annotations

import pytest

from domain.execution.services.graph_runtime.edge_evaluator import SubstituteVal
from exceptions.service_exceptions import DomainValidationException


def test_resolve_raises_when_context_none() -> None:
    sv = SubstituteVal([["a"]])
    with pytest.raises(DomainValidationException):
        sv.resolve(None)


def test_resolve_dict_missing_key() -> None:
    sv = SubstituteVal([["missing"]])
    with pytest.raises(DomainValidationException):
        sv.resolve({})


def test_resolve_list_of_dicts_by_name() -> None:
    sv = SubstituteVal([["x"]])
    assert sv.resolve([{"x": 1}, {"x": 2}]) == [1, 2]


def test_resolve_with_numeric_index() -> None:
    sv = SubstituteVal([["arr", 1]])
    assert sv.resolve({"arr": [10, 20, 30]}) == 20


def test_resolve_attribute_path() -> None:
    class Obj:
        name = "n"

    sv = SubstituteVal([["name"]])
    assert sv.resolve(Obj()) == "n"
