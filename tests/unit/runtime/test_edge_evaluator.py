import pytest

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from exceptions.service_exceptions import DomainValidationException


def test_edge_evaluator_returns_true_for_valid_condition():
    context = {"validation_status": "VALID", "confidence": 0.9}
    assert EdgeEvaluator.is_true("validation_status == 'VALID' and confidence >= 0.85", context)


def test_edge_evaluator_returns_false_for_invalid_condition():
    context = {"validation_status": "INVALID", "confidence": 0.5}
    assert not EdgeEvaluator.is_true("validation_status == 'VALID' and confidence >= 0.85", context)


def test_edge_evaluator_handles_comparison_operators():
    context = {"value": 10}
    assert EdgeEvaluator.is_true("value > 5", context)
    assert EdgeEvaluator.is_true("value >= 10", context)
    assert EdgeEvaluator.is_true("value < 20", context)
    assert EdgeEvaluator.is_true("value <= 10", context)
    assert not EdgeEvaluator.is_true("value > 20", context)


def test_edge_evaluator_handles_not_operator():
    context = {"flag": True}
    assert EdgeEvaluator.is_true("not flag == False", context)
    assert not EdgeEvaluator.is_true("not flag == True", context)


def test_edge_evaluator_handles_or_operator():
    context = {"status": "ERROR"}
    assert EdgeEvaluator.is_true("status == 'ERROR' or status == 'FAILED'", context)
    assert EdgeEvaluator.is_true("status == 'SUCCESS' or status == 'ERROR'", context)
    assert not EdgeEvaluator.is_true("status == 'SUCCESS' or status == 'PENDING'", context)


def test_edge_evaluator_raises_on_invalid_syntax():
    context = {"value": 10}
    with pytest.raises(DomainValidationException, match="edge_condition_invalid"):
        EdgeEvaluator.is_true("foo(", context)


def test_edge_evaluator_raises_on_unsupported_operation():
    context = {"value": 10}
    with pytest.raises(DomainValidationException, match="edge_condition_invalid"):
        EdgeEvaluator.is_true("value + 5", context)
