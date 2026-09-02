from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GraphStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    current_node_id: str | None = None
    resume_to_node_id: str | None = None
    state: dict[str, object] = Field(default_factory=dict)
    memory: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
