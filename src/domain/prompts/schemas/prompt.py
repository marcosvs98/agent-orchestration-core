from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PromptIntent(StrEnum):
    INTENT_TOOL_SELECTION = "intent_tool_selection"
    PARAM_EXTRACTION = "param_extraction"
    SLOT_FILLING = "slot_filling"
    CLARIFICATION = "clarification"
    RESPONSE_RENDER = "response_render"


class NodeType(StrEnum):
    UserContextEnrichmentNode = "UserContextEnrichmentNode"

    IntentDetectionNode = "IntentDetectionNode"
    ParamExtractionNode = "ParamExtractionNode"

    ClarificationNode = "ClarificationNode"

    ToolSelectionNode = "ToolSelectionNode"
    ToolExecutionNode = "ToolExecutionNode"
    ToolErrorHandlerNode = "ToolErrorHandlerNode"

    ResponseComposer = "ResponseComposer"
    FallbackNodeSLA = "FallbackNodeSLA"


class NodePrompt(BaseModel):
    prompt_id: UUID
    node_type: str
    template_text: str
    input_schema: Dict[str, Any] | None = None
    output_schema: Dict[str, Any] | None = None
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
    input_schema: Dict[str, Any] | None = None
    output_schema: Dict[str, Any] | None = None
    description: str | None = None
    created_by: str | None = None

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        valid_types: set[str] = {node_type.value for node_type in NodeType}
        if v not in valid_types:
            raise ValueError(f"node_type must be one of {', '.join(valid_types)}")
        return v


class NodePromptUpdate(BaseModel):
    template_text: str | None = Field(None, min_length=1)
    input_schema: Dict[str, Any] | None = None
    output_schema: Dict[str, Any] | None = None
    description: str | None = None


class ResolvedPrompt(BaseModel):
    prompt_text: str
    input_schema: Dict[str, Any] | None = None
    output_schema: Dict[str, Any] | None = None
    prompt_id: UUID | None = None
    prompt_version: int | None = None
    prompt_frozen_hash: str | None = None

    model_config = {"frozen": True}
