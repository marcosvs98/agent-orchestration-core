from __future__ import annotations

from typing import Protocol

from domain.llm.schemas.agent_turn import AgentTurnCompletion, AgentTurnRequest


class AgentLLMPort(Protocol):
    """Single tool-capable inference turn.

    Distinct from ``LLMProviderPort.infer``, which answers with structured JSON for a node and
    has no notion of a tool call. Here the model may answer with text, with tool calls, or with
    both; the caller owns the loop that executes the calls and asks again.
    """

    async def complete_agent_turn(
        self, request: AgentTurnRequest
    ) -> AgentTurnCompletion:  # pragma: no cover - interface
        ...
