from __future__ import annotations

import ast
from collections import defaultdict
from typing import Dict, List

from pydantic import ValidationError as PydanticValidationError

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge
from domain.flows.schemas.graph_node_config import validate_node_config
from domain.flows.services.flow_graph_validator import FlowGraphValidator
from exceptions.service_exceptions import DomainValidationException


class FlowGraphDraftValidator:
    """Fail-fast validation for flow graph drafts (DRAFT -> VALIDATED)."""

    @staticmethod
    def validate(definition: FlowGraphDefinition) -> None:
        FlowGraphValidator.validate(definition)
        FlowGraphDraftValidator._validate_node_configs(definition)
        FlowGraphDraftValidator._validate_edge_syntax(definition.edges)
        FlowGraphDraftValidator._validate_mutual_exclusion(definition.edges)
        FlowGraphDraftValidator._validate_cycles(definition)

    @staticmethod
    def _validate_node_configs(definition: FlowGraphDefinition) -> None:
        for node_id, spec in definition.nodes.items():
            try:
                validate_node_config(spec.type, spec.config)
            except PydanticValidationError as exc:
                raise DomainValidationException(
                    message="node_config_invalid",
                    detail={
                        "node_id": node_id,
                        "type": spec.type,
                        "errors": exc.errors(),
                    },
                ) from exc

    @staticmethod
    def _validate_edge_syntax(edges: List[FlowGraphEdge]) -> None:
        for edge in edges:
            try:
                EdgeEvaluator.compile_condition(edge.condition)
            except DomainValidationException as exc:
                raise exc from exc

    @staticmethod
    def _validate_mutual_exclusion(edges: List[FlowGraphEdge]) -> None:
        by_from: Dict[str, List[FlowGraphEdge]] = defaultdict(list)
        for edge in edges:
            by_from[edge.from_node].append(edge)

        for edge_list in by_from.values():
            if len(edge_list) < 2:
                continue
            seen = set()
            for edge in edge_list:
                if edge.condition in seen:
                    raise DomainValidationException(message="edge_condition_duplicate")
                seen.add(edge.condition)
            if FlowGraphDraftValidator._has_always_true(edge_list):
                raise DomainValidationException(message="edge_condition_not_mutually_exclusive")

    @staticmethod
    def _has_always_true(edge_list: List[FlowGraphEdge]) -> bool:
        for edge in edge_list:
            try:
                expr = edge.condition.replace("&&", " and ").replace("||", " or ")
                tree = ast.parse(expr, mode="eval")
                if FlowGraphDraftValidator._is_constant_true(tree.body):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _is_constant_true(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return bool(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return FlowGraphDraftValidator._is_constant_true(node.operand) is False
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(FlowGraphDraftValidator._is_constant_true(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(FlowGraphDraftValidator._is_constant_true(v) for v in node.values)
        if isinstance(node, ast.Compare):
            # evaluate only when both sides are constants
            if len(node.ops) == 1 and len(node.comparators) == 1:
                left = node.left
                right = node.comparators[0]
                if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    return (
                        eval(compile(ast.Expression(node), "<ast>", "eval")) is True  # pylint: disable=eval-used
                    )  # safe because constants only
        return False

    @staticmethod
    def _validate_cycles(definition: FlowGraphDefinition) -> None:
        adjacency = defaultdict(list)
        edge_kind_map: Dict[tuple[str, str], str] = {}
        for edge in definition.edges:
            adjacency[edge.from_node].append(edge.to_node)
            edge_kind_map[(edge.from_node, edge.to_node)] = edge.edge_kind

        visiting = set()
        visited = set()

        def dfs(node_id: str) -> None:
            if node_id in visiting:
                return
            visiting.add(node_id)
            for nxt in adjacency.get(node_id, []):
                if nxt in visiting:
                    kind = edge_kind_map.get((node_id, nxt))
                    if kind != "LOOP":
                        raise DomainValidationException(message="cycle_not_marked_loop")
                if nxt not in visited:
                    dfs(nxt)
            visiting.remove(node_id)
            visited.add(node_id)

        dfs(definition.start_node)
