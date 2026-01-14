from __future__ import annotations

from typing import Dict, List, Set

from pydantic import BaseModel


class CompiledEdge(BaseModel):
    from_node: str
    to_node: str
    edge_kind: str
    compiled_condition: dict
    order: int

    model_config = {"frozen": True}


class ExecutionPlan(BaseModel):
    start_node_id: str
    ordered_nodes: List[str]
    adjacency_map: Dict[str, List[CompiledEdge]]
    terminal_nodes: Set[str]
    structural_hash: str
    nodes: Dict[str, Dict]

    model_config = {"frozen": True}
