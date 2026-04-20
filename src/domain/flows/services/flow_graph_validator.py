from __future__ import annotations

from typing import Set

from domain.flows.schemas.graph import FlowGraphDefinition
from exceptions.service_exceptions import DomainValidationException


TERMINAL_NODE_TYPES = {"ResponseBuilder", "HumanFallback"}

_DEPRECATED_NODE_TYPES = frozenset({"UserContextEnrichmentNode"})

_RAG_PIPELINE_NODE_TYPES = frozenset(
    {
        "IntentClassifier",
        "ToolResolver",
        "ToolInputFiller",
        "ResponseBuilder",
        "HumanFallback",
    }
)


class FlowGraphValidator:
    """Static validation for flow graph definitions."""

    @staticmethod
    def validate(definition: FlowGraphDefinition) -> None:
        nodes = definition.nodes
        for _nid, spec in nodes.items():
            if spec.type in _DEPRECATED_NODE_TYPES:
                raise DomainValidationException(
                    message="deprecated_node_type_user_context_enrichment"
                )
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

        for _node_id, spec in nodes.items():
            if spec.type not in _RAG_PIPELINE_NODE_TYPES:
                continue
            cfg = spec.config or {}
            rp = cfg.get("rag_pipeline")
            if rp is not None and not isinstance(rp, dict):
                raise DomainValidationException(message="rag_pipeline_config_invalid")

        memory_commit_ids = [
            node_id for node_id, spec in nodes.items() if spec.type == "MemoryCommitNode"
        ]
        if len(memory_commit_ids) > 1:
            raise DomainValidationException(message="multiple_memory_commit_nodes")
        for node_id, spec in nodes.items():
            if spec.type != "MemoryCommitNode":
                continue
            cfg = spec.config or {}
            dm = cfg.get("data_merge")
            if not isinstance(dm, list):
                continue
            for rule in dm:
                if not isinstance(rule, dict):
                    raise DomainValidationException(message="memory_commit_data_merge_rule_invalid")
                fid = rule.get("from_node_id")
                if not fid or fid not in nodes:
                    raise DomainValidationException(
                        message="memory_commit_data_merge_unknown_from_node"
                    )
