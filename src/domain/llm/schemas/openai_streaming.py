from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from domain.llm.schemas.llm import LLMMessage


class OpenAIStreamingRequest(BaseModel):
    model_alias: str
    input_messages: list[LLMMessage] = Field(default_factory=list)
    principal_id: str | None = None
    conversation_key: str | None = None
    history_mode: Literal["manual", "provider_conversation"]
    tools: list[dict[str, object]] = Field(default_factory=list)
    temperature: float = 0.2

    @model_validator(mode="after")
    def _validate_history_mode(self) -> "OpenAIStreamingRequest":
        if self.history_mode == "provider_conversation" and not self.conversation_key:
            raise ValueError("conversation_key_required_for_provider_conversation")
        return self
