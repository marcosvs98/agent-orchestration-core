from __future__ import annotations

import pytest

from domain.flows.services.condition_evaluator import ConditionEvaluator


class TestConditionEvaluator:
    def test_evaluate_simple_equality(self) -> None:
        assert ConditionEvaluator.evaluate("a == 1", {"a": 1}) is True
        assert ConditionEvaluator.evaluate("a == 1", {"a": 2}) is False

    def test_evaluate_and_or_aliases(self) -> None:
        assert ConditionEvaluator.evaluate("x > 1 && x < 10", {"x": 5}) is True
        assert ConditionEvaluator.evaluate("x < 2 || x > 20", {"x": 1}) is True

    def test_evaluate_not(self) -> None:
        assert ConditionEvaluator.evaluate("not flag", {"flag": False}) is True

    def test_rejects_unsafe_expression(self) -> None:
        with pytest.raises(ValueError, match="expression_not_allowed"):
            ConditionEvaluator.evaluate("foo()", {})
