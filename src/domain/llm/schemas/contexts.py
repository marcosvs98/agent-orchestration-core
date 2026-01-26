from uuid import UUID

from pydantic import BaseModel

from domain.agents.schemas.agents import PersonaConfig
from domain.execution.services.graph_runtime.types import ExecutionContext


class IntentDetectionContext(BaseModel):
    persona: PersonaConfig
    user_input: str
    context: ExecutionContext


class SlotFillingContext(BaseModel):
    persona: PersonaConfig
    intent: str
    tool_config_id: UUID
    request_schema: dict


class ResponseFormattingContext(BaseModel):
    persona: PersonaConfig
    tool_response: dict
    original_intent: str
