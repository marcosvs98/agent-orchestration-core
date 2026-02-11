from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PromptIntent(StrEnum):
    INTENT_TOOL_SELECTION = "INTENT_TOOL_SELECTION"
    PARAM_EXTRACTION = "PARAM_EXTRACTION"
    SLOT_FILLING = "SLOT_FILLING"
    CLARIFICATION = "CLARIFICATION"
    RESPONSE_RENDER = "RESPONSE_RENDER"


class NodeType(StrEnum):
    IntentToolSelectionNode = "IntentToolSelectionNode"
    ParamExtractionNode = "ParamExtractionNode"
    ClarificationNode = "ClarificationNode"
    ResponseNode = "ResponseNode"
    ToolExecutionNode = "ToolExecutionNode"
    UserContextEnrichmentNode = "UserContextEnrichmentNode"
    FallbackNode = "FallbackNode"


class NodePrompt(BaseModel):
    prompt_id: UUID
    node_type: str
    template_text: str
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    version: int
    frozen_hash: str
    is_active: bool
    description: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}


class NodePromptCreate(BaseModel):
    node_type: str
    template_text: str = Field(..., min_length=1)
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    description: str | None = None
    created_by: str | None = None

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        valid_types: set[str] = {
            NodeType.IntentToolSelectionNode.value,
            NodeType.ParamExtractionNode.value,
            NodeType.ClarificationNode.value,
            NodeType.ResponseNode.value,
        }
        if v not in valid_types:
            raise ValueError(f"node_type must be one of {', '.join(valid_types)}")
        return v


class NodePromptUpdate(BaseModel):
    template_text: str | None = Field(None, min_length=1)
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    description: str | None = None


class ResolvedPrompt(BaseModel):
    prompt_text: str
    input_schema: Dict[str, Any] | None = None
    output_schema: Dict[str, Any] | None = None
    prompt_id: UUID | None = None
    prompt_version: int | None = None
    prompt_frozen_hash: str | None = None

    model_config = {"frozen": True}
