from __future__ import annotations

import ast
import hashlib
import json
from typing import Any, Dict, List

from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge
from exceptions.service_exceptions import DomainValidationException


class ConditionCompiler(ast.NodeVisitor):
    ALLOWED_BINOPS = {ast.And, ast.Or}
    ALLOWED_CMP = {ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE}

    def compile(self, condition: str) -> Dict[str, Any]:
        expr = condition.replace("&&", " and ").replace("||", " or ")
        try:
            parsed = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise DomainValidationException(message="edge_condition_invalid") from exc
        return self.visit(parsed.body)

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BoolOp):
            if type(node.op) not in self.ALLOWED_BINOPS:
                raise DomainValidationException(message="edge_condition_not_supported")
            op = "AND" if isinstance(node.op, ast.And) else "OR"
            return {"type": "bool_op", "op": op, "values": [self.visit(v) for v in node.values]}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return {"type": "not", "value": self.visit(node.operand)}
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise DomainValidationException(message="edge_condition_not_supported")
            op = node.ops[0]
            if type(op) not in self.ALLOWED_CMP:
                raise DomainValidationException(message="edge_condition_not_supported")
            return {
                "type": "compare",
                "op": op.__class__.__name__,
                "left": self.visit(node.left),
                "right": self.visit(node.comparators[0]),
            }
        if isinstance(node, ast.Name):
            return {"type": "identifier", "value": node.id}
        if isinstance(node, ast.Constant):
            return {"type": "constant", "value": node.value}
        raise DomainValidationException(message="edge_condition_not_supported")


class FlowGraphCompiler:
    def __init__(self) -> None:
        self.condition_compiler = ConditionCompiler()

    def compile(self, definition: FlowGraphDefinition) -> tuple[Dict[str, Any], str]:
        edges = self._compile_edges(definition.edges)
        snapshot = {
            "start_node": definition.start_node,
            "nodes": {k: v.model_dump() for k, v in definition.nodes.items()},
            "edges": edges,
            "schema_version": 1,
        }
        hash_input = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        graph_hash = hashlib.sha256(hash_input).hexdigest()
        return snapshot, graph_hash

    def _compile_edges(self, edges: List[FlowGraphEdge]) -> List[Dict[str, Any]]:
        compiled: List[Dict[str, Any]] = []
        for edge in sorted(edges, key=lambda e: (e.from_node, e.to_node, e.condition)):
            compiled.append(
                {
                    "from_node": edge.from_node,
                    "to_node": edge.to_node,
                    "edge_kind": edge.edge_kind,
                    "condition": edge.condition,
                    "compiled_condition": self.condition_compiler.compile(edge.condition),
                }
            )
        return compiled
