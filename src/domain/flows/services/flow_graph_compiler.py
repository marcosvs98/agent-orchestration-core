from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from domain.execution.services.graph_runtime.edge_evaluator import EdgeEvaluator
from domain.flows.schemas.graph import FlowGraphDefinition, FlowGraphEdge


class ConditionCompiler:
    def compile(self, condition: str) -> Any:
        return EdgeEvaluator.compile_condition(condition)


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
        hash_input = json.dumps(
            snapshot, sort_keys=True, separators=(",", ":")
        ).encode()
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
                    "compiled_condition": self.condition_compiler.compile(
                        edge.condition
                    ),
                }
            )
        return compiled
