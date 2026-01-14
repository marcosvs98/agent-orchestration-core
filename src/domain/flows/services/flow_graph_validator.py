from __future__ import annotations

from typing import Set

from domain.flows.schemas.graph import FlowGraphDefinition
from exceptions.service_exceptions import DomainValidationException


TERMINAL_NODE_TYPES = {"ResponseNode", "FallbackNode"}


class FlowGraphValidator:
    """Static validation for flow graph definitions."""

    @staticmethod
    def validate(definition: FlowGraphDefinition) -> None:
        nodes = definition.nodes
        if definition.start_node not in nodes:
            raise DomainValidationException(message="start_node_not_found")

        node_keys = set(nodes.keys())
        for edge in definition.edges:
            if edge.from_node not in node_keys or edge.to_node not in node_keys:
                raise DomainValidationException(message="edge_references_unknown_node")
            if not edge.condition or not edge.condition.strip():
                raise DomainValidationException(message="edge_condition_required")

        # reachability
        adjacency: dict[str, set[str]] = {k: set() for k in node_keys}
        for edge in definition.edges:
            adjacency[edge.from_node].add(edge.to_node)

        visited: Set[str] = set()

        def dfs(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for nxt in adjacency.get(node_id, set()):
                dfs(nxt)

        dfs(definition.start_node)
        if visited != node_keys:
            raise DomainValidationException(message="unreachable_nodes")

        # termination: every path must end in terminal node type
        terminals = {k for k, v in nodes.items() if v.type in TERMINAL_NODE_TYPES}
        if not terminals:
            raise DomainValidationException(message="no_terminal_nodes")

        def has_terminal_path(node_id: str, seen: set[str]) -> bool:
            if node_id in seen:
                return False
            if node_id in terminals:
                return True
            seen = set(seen)
            seen.add(node_id)
            nexts = adjacency.get(node_id, set())
            if not nexts:
                return False
            return any(has_terminal_path(nxt, seen) for nxt in nexts)

        if not has_terminal_path(definition.start_node, set()):
            raise DomainValidationException(message="no_terminal_path")
