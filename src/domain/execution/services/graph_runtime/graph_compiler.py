from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set


from domain.execution.services.graph_runtime.execution_plan import (
    AvailableTool,
    CompiledEdge,
    ExecutionPlan,
)
from domain.flows.schemas.graph import EdgeKind
from exceptions.service_exceptions import DomainValidationException


class GraphCompiler:
    """Pure compiler: flow_graph_snapshot -> ExecutionPlan."""

    def compile(
        self,
        snapshot: Dict[str, Any],
        structural_hash: str,
        available_tools: list[AvailableTool] | None = None,
    ) -> ExecutionPlan:
        start_node = snapshot.get("start_node")
        nodes = snapshot.get("nodes", {})
        edges = snapshot.get("edges", [])
        if not start_node or start_node not in nodes:
            raise DomainValidationException(message="start_node_not_found")
        if not edges:
            raise DomainValidationException(message="edges_required")

        adjacency: dict[str, list[CompiledEdge]] = defaultdict(list)
        ordered_nodes: List[str] = list(nodes.keys())
        terminal_nodes: Set[str] = set(
            [
                node_id
                for node_id, spec in nodes.items()
                if spec.get("type")
                in {"ResponseNode", "FallbackNode"}  # Todo: Usar StrEnum's aqui
            ]
        )
        if not terminal_nodes:
            raise DomainValidationException(message="no_terminal_nodes")

        for order, edge in enumerate(
            sorted(
                edges,
                key=lambda e: (
                    e.get("from_node"),
                    e.get("to_node"),
                    e.get("condition", ""),
                ),
            )
        ):
            compiled = edge.get("compiled_condition")
            if compiled is None:
                raise DomainValidationException(message="compiled_condition_missing")
            edge_kind_str = edge.get("edge_kind", EdgeKind.NORMAL.value)
            edge_kind = (
                EdgeKind(edge_kind_str)
                if isinstance(edge_kind_str, str)
                else edge_kind_str
            )
            ce = CompiledEdge(
                from_node=edge.get("from_node"),
                to_node=edge.get("to_node"),
                edge_kind=edge_kind,
                compiled_condition=compiled,
                order=order,
            )
            adjacency[ce.from_node].append(ce)

        self._validate_reachability(start_node, adjacency, nodes.keys())
        self._validate_loops(adjacency)

        return ExecutionPlan(
            start_node_id=start_node,
            ordered_nodes=ordered_nodes,
            adjacency_map=dict(adjacency),
            terminal_nodes=terminal_nodes,
            structural_hash=structural_hash,
            nodes=nodes,
            available_tools=available_tools or [],
        )

    def _validate_reachability(
        self, start_node: str, adjacency: dict[str, list[CompiledEdge]], node_ids: Any
    ) -> None:
        visited: Set[str] = set()

        def dfs(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for edge in adjacency.get(node_id, []):
                dfs(edge.to_node)

        dfs(start_node)
        if set(node_ids) != visited:
            raise DomainValidationException(message="unreachable_nodes")

    def _validate_loops(self, adjacency: dict[str, list[CompiledEdge]]) -> None:
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def dfs(node_id: str) -> None:
            if node_id in visiting:
                return
            visiting.add(node_id)
            for edge in adjacency.get(node_id, []):
                if edge.to_node in visiting and edge.edge_kind != EdgeKind.LOOP:
                    raise DomainValidationException(message="cycle_not_marked_loop")
                if edge.to_node not in visited:
                    dfs(edge.to_node)
            visiting.remove(node_id)
            visited.add(node_id)

        for node in adjacency.keys():
            if node not in visited:
                dfs(node)
