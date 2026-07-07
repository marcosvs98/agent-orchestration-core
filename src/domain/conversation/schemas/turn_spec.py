from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from domain.llm.schemas.llm import LLMMessage
from domain.llm.schemas.openai_streaming import OpenAIStreamingRequest


class ConversationPromptPart(BaseModel):
    source: Literal[
        "agent_system_prompt",
        "runtime_rules",
        "selected_user_prompt",
        "rag_context",
        "message_history",
        "current_user_input",
    ]
    role: Literal["system", "developer", "user", "assistant"]
    content: str
    trust_level: Literal[
        "trusted_instruction",
        "tenant_managed",
        "retrieved_untrusted",
        "user_supplied",
    ]
    provenance: dict[str, str | int | bool | None] = Field(default_factory=dict)


class ConversationTurnSpec(BaseModel):
    model_alias: str
    prompt_parts: list[ConversationPromptPart] = Field(default_factory=list)
    user_message: str
    history_mode: Literal["manual", "provider_conversation"]
    conversation_key: str | None = None
    principal_id: str
    tools: list[dict[str, object]] = Field(default_factory=list)
    trace_metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_history_mode(self) -> "ConversationTurnSpec":
        if self.history_mode == "provider_conversation" and not self.conversation_key:
            raise ValueError("conversation_key_required_for_provider_conversation")
        return self

    def to_streaming_request(self) -> OpenAIStreamingRequest:
        input_messages = [
            LLMMessage(role=part.role, content=part.content)
            for part in self.prompt_parts
            if part.content
        ]
        if not input_messages or input_messages[-1].content != self.user_message:
            input_messages.append(LLMMessage(role="user", content=self.user_message))
        return OpenAIStreamingRequest(
            model_alias=self.model_alias,
            input_messages=input_messages,
            principal_id=self.principal_id,
            conversation_key=self.conversation_key,
            history_mode=self.history_mode,
            tools=self.tools,
        )
