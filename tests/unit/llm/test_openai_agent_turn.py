"""Tool-capable inference turn against the OpenAI Responses API.

The agent runtime depends on two things this adapter must get right: pairing every assistant
``function_call`` with its ``function_call_output`` when the transcript is replayed, and reading
the model's tool calls back out of the response.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.schemas.agent_turn import (
    AgentToolCall,
    AgentToolDefinition,
    AgentTurnMessage,
    AgentTurnRequest,
    AgentTurnRole,
    AgentTurnStopReason,
)
from exceptions.service_exceptions import DomainValidationException


def _block(payload: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.model_dump.return_value = payload
    return block


def _response(output: list[MagicMock]) -> MagicMock:
    response = MagicMock()
    response.id = "resp-1"
    response.output = output
    usage = MagicMock()
    usage.input_tokens = 12
    usage.output_tokens = 3
    usage.total_tokens = 15
    usage.input_tokens_details = None
    response.usage = usage
    return response


def _adapter(response: MagicMock) -> tuple[OpenAIProviderAdapter, list[dict]]:
    payloads: list[dict] = []

    async def _create(**kwargs: Any) -> MagicMock:
        payloads.append(dict(kwargs))
        return response

    cache = MagicMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_create)
    return (
        OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client),
        payloads,
    )


@pytest.mark.asyncio
async def test_tools_are_sent_as_function_definitions() -> None:
    adapter, payloads = _adapter(
        _response([_block({"type": "message", "content": [{"type": "output_text", "text": "hi"}]})])
    )

    completion = await adapter.complete_agent_turn(
        request=AgentTurnRequest(
            model_alias="gpt-4.1",
            messages=[AgentTurnMessage(role=AgentTurnRole.USER, content="hello")],
            tools=[
                AgentToolDefinition(
                    name="search",
                    description="search things",
                    parameters={"type": "object", "properties": {}},
                )
            ],
            principal_id="principal",
        )
    )

    payload = payloads[0]
    assert payload["tools"] == [
        {
            "type": "function",
            "name": "search",
            "description": "search things",
            "parameters": {"type": "object", "properties": {}},
        }
    ]
    assert payload["tool_choice"] == "auto"
    assert payload["user"] == "principal"
    assert completion.text == "hi"
    assert completion.stop_reason is AgentTurnStopReason.OUTPUT


@pytest.mark.asyncio
async def test_tool_calls_are_parsed_out_of_the_response() -> None:
    adapter, _ = _adapter(
        _response(
            [
                _block(
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "search",
                        "arguments": '{"query": "weather"}',
                    }
                )
            ]
        )
    )

    completion = await adapter.complete_agent_turn(
        request=AgentTurnRequest(
            model_alias="gpt-4.1",
            messages=[AgentTurnMessage(role=AgentTurnRole.USER, content="hello")],
        )
    )

    assert completion.stop_reason is AgentTurnStopReason.TOOL_CALLS
    assert completion.tool_calls == [
        AgentToolCall(
            call_id="call-1",
            name="search",
            arguments={"query": "weather"},
            raw_arguments='{"query": "weather"}',
        )
    ]
    assert completion.token_usage["input_tokens"] == 12


@pytest.mark.asyncio
async def test_a_replayed_transcript_pairs_calls_with_their_outputs() -> None:
    adapter, payloads = _adapter(
        _response([_block({"type": "message", "content": [{"type": "output_text", "text": "ok"}]})])
    )
    tool_call = AgentToolCall(
        call_id="call-1", name="search", arguments={"query": "x"}, raw_arguments='{"query": "x"}'
    )

    await adapter.complete_agent_turn(
        request=AgentTurnRequest(
            model_alias="gpt-4.1",
            messages=[
                AgentTurnMessage(role=AgentTurnRole.SYSTEM, content="You are an agent."),
                AgentTurnMessage(role=AgentTurnRole.USER, content="find it"),
                AgentTurnMessage(role=AgentTurnRole.ASSISTANT, content="", tool_calls=[tool_call]),
                AgentTurnMessage(
                    role=AgentTurnRole.TOOL,
                    content='{"body": {"found": true}}',
                    tool_call_id="call-1",
                    tool_name="search",
                ),
            ],
        )
    )

    items = payloads[0]["input"]
    assert items[0] == {"role": "system", "content": "You are an agent."}
    assert items[1] == {"role": "user", "content": "find it"}
    assert items[2] == {
        "type": "function_call",
        "call_id": "call-1",
        "name": "search",
        "arguments": '{"query": "x"}',
    }
    assert items[3] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": '{"body": {"found": true}}',
    }


@pytest.mark.asyncio
async def test_provider_failures_surface_as_a_domain_error_without_leaking_the_payload() -> None:
    cache = MagicMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=RuntimeError("boom"))
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)

    with pytest.raises(DomainValidationException) as exc_info:
        await adapter.complete_agent_turn(
            request=AgentTurnRequest(
                model_alias="gpt-4.1",
                messages=[AgentTurnMessage(role=AgentTurnRole.USER, content="hello")],
            )
        )

    assert exc_info.value.message == "llm_provider_error"
    assert "messages" not in exc_info.value.input_data
    assert exc_info.value.input_data["message_count"] == 1
