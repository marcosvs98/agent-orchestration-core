from __future__ import annotations

from typing import Any, Dict

from domain.flows.services.condition_evaluator import ConditionEvaluator
from exceptions.service_exceptions import DomainValidationException


class EdgeEvaluator:
    @staticmethod
    def is_true(condition: str, context: Dict[str, Any], compiled_condition: Dict[str, Any] | None = None) -> bool:
        """Evaluate an edge condition safely against node output."""
        try:
            if compiled_condition is not None:
                return EdgeEvaluator._eval_compiled(compiled_condition, context)
            return ConditionEvaluator.evaluate(condition, context)
        except Exception as exc:
            raise DomainValidationException(message="edge_evaluation_error") from exc

    @staticmethod
    def _eval_compiled(node: Dict[str, Any], context: Dict[str, Any]) -> Any:
        node_type = node.get("type")
        if node_type == "bool_op":
            op = node.get("op")
            values = [EdgeEvaluator._eval_compiled(v, context) for v in node.get("values", [])]
            if op == "AND":
                return all(values)
            if op == "OR":
                return any(values)
        if node_type == "not":
            return not EdgeEvaluator._eval_compiled(node.get("value"), context)
        if node_type == "compare":
            left = EdgeEvaluator._eval_compiled(node.get("left"), context)
            right = EdgeEvaluator._eval_compiled(node.get("right"), context)
            op = node.get("op")
            if op == "Eq":
                return left == right
            if op == "NotEq":
                return left != right
            if op == "Lt":
                return left < right
            if op == "LtE":
                return left <= right
            if op == "Gt":
                return left > right
            if op == "GtE":
                return left >= right
        if node_type == "identifier":
            return context.get(node.get("value"))
        if node_type == "constant":
            return node.get("value")
        raise DomainValidationException(message="edge_condition_not_supported")
