from __future__ import annotations

import ast
from typing import Any, Mapping


class _SafeEvaluator(ast.NodeVisitor):
    ALLOWED_BINOPS = {ast.And, ast.Or}
    ALLOWED_CMP = {
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    }

    def __init__(self, context: Mapping[str, Any]) -> None:
        self.context = context

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BoolOp):
            if type(node.op) not in self.ALLOWED_BINOPS:
                raise ValueError("boolop_not_allowed")
            values = [self.visit(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            return any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self.visit(node.operand)
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("chained_compare_not_supported")
            op = node.ops[0]
            if type(op) not in self.ALLOWED_CMP:
                raise ValueError("compare_not_allowed")
            left = self.visit(node.left)
            right = self.visit(node.comparators[0])
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
        if isinstance(node, ast.Name):
            return self.context.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError("expression_not_allowed")


class ConditionEvaluator:
    """Safe evaluator for simple boolean expressions on NodeOutput."""

    @staticmethod
    def evaluate(condition: str, context: Mapping[str, Any]) -> bool:
        expr = condition.replace("&&", " and ").replace("||", " or ")
        parsed = ast.parse(expr, mode="eval")
        visitor = _SafeEvaluator(context)
        result = visitor.visit(parsed.body)  # type: ignore[arg-type]
        return bool(result)
