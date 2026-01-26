from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, field_validator


class EdgeKind(StrEnum):
    NORMAL = "NORMAL"
    LOOP = "LOOP"


class FlowGraphNodeSpec(BaseModel):
    type: str
    config: Dict[str, Any] | None = None


class FlowGraphEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str
    edge_kind: EdgeKind = EdgeKind.NORMAL

    @field_validator("condition")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("condition_required")
        return value


class FlowGraphDefinition(BaseModel):
    start_node: str
    nodes: Dict[str, FlowGraphNodeSpec]
    edges: List[FlowGraphEdge]


class FlowGraphCreate(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    definition: FlowGraphDefinition
    principal_id: str


class FlowGraphDraftCreate(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    definition: FlowGraphDefinition
    principal_id: str


class FlowGraphCompileRequest(BaseModel):
    flow_id: UUID
    flow_version_id: UUID
    principal_id: str
