from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.schemas.llm import LLMMessage
from domain.llm.schemas.openai_streaming import OpenAIStreamingRequest
from exceptions.service_exceptions import DomainValidationException


def _fake_response() -> MagicMock:
    resp = MagicMock()
    resp.id = "resp-001"
    resp.output = []
    resp.usage = None
    resp.model_dump.return_value = {}
    return resp


@pytest.mark.asyncio
async def test_infer_streaming_request_builds_ordered_payload() -> None:
    payloads: list[dict] = []

    async def _fake_create(**kwargs: Any) -> Any:
        payloads.append(dict(kwargs))

        async def _events() -> AsyncGenerator:
            completed = MagicMock()
            completed.model_dump.return_value = {"type": "response.completed", "response": {}}
            completed.response = _fake_response()
            yield completed

        return _events()

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    openai_client.conversations.create = AsyncMock(return_value=MagicMock(id="conv-1"))
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)

    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[
            LLMMessage(role="system", content="System"),
            LLMMessage(role="developer", content="Rules"),
            LLMMessage(role="user", content="Question"),
        ],
        principal_id="user-1",
        conversation_key="tenant:session",
        history_mode="provider_conversation",
    )

    await adapter.infer_streaming_request(request=request)

    payload = payloads[0]
    assert payload["model"] == "gpt-4.1"
    assert payload["input"] == [
        {"role": "system", "content": "System"},
        {"role": "developer", "content": "Rules"},
        {"role": "user", "content": "Question"},
    ]
    assert payload["user"] == "user-1"
    assert payload["conversation"] == "conv-1"
    assert "instructions" not in payload


@pytest.mark.asyncio
async def test_infer_streaming_request_manual_history_omits_conversation() -> None:
    payloads: list[dict] = []

    async def _fake_create(**kwargs: Any) -> Any:
        payloads.append(dict(kwargs))

        async def _events() -> AsyncGenerator:
            completed = MagicMock()
            completed.model_dump.return_value = {"type": "response.completed", "response": {}}
            completed.response = _fake_response()
            yield completed

        return _events()

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    openai_client.conversations.create = AsyncMock(return_value=MagicMock(id="conv-1"))
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)

    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[
            LLMMessage(role="system", content="System"),
            LLMMessage(role="user", content="Question"),
        ],
        principal_id="user-1",
        history_mode="manual",
    )

    await adapter.infer_streaming_request(request=request)

    payload = payloads[0]
    assert "conversation" not in payload


@pytest.mark.asyncio
async def test_infer_streaming_request_exposes_provider_error_payload_for_debug() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=RuntimeError("boom"))
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[LLMMessage(role="user", content="secret question")],
        principal_id="user-1",
        history_mode="manual",
    )

    with pytest.raises(DomainValidationException) as raised:
        await adapter.infer_streaming_request(request=request)

    assert raised.value.input_data["model"] == "gpt-4.1"
    assert raised.value.input_data["input"] == [{"role": "user", "content": "secret question"}]
    assert raised.value.input_data["store"] is False
    assert "secret question" in str(raised.value.input_data)


@pytest.mark.asyncio
async def test_infer_streaming_request_disables_retry_when_tools_present() -> None:
    payloads: list[dict] = []

    async def _fake_create(**kwargs: Any) -> Any:
        payloads.append(dict(kwargs))
        raise RuntimeError("Error code: 424 - Failed Dependency")

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[LLMMessage(role="user", content="Question")],
        principal_id="user-1",
        history_mode="manual",
        tools=[
            {
                "type": "mcp",
                "server_label": "tenant-mcp",
                "server_url": "https://mcp.example.com/mcp",
                "require_approval": "never",
                "headers": {"x-api-key": "x", "authorization": "Bearer y"},
            }
        ],
    )

    with pytest.raises(DomainValidationException):
        await adapter.infer_streaming_request(request=request)

    assert openai_client.responses.create.await_count == 1
    assert "tools" in payloads[0]


@pytest.mark.asyncio
async def test_infer_streaming_request_retries_424_without_tools() -> None:
    payloads: list[dict] = []
    calls = {"value": 0}

    async def _fake_create(**kwargs: Any) -> Any:
        payloads.append(dict(kwargs))
        calls["value"] += 1
        if calls["value"] == 1:
            raise RuntimeError("Error code: 424 - Failed Dependency")

        async def _events() -> AsyncGenerator:
            completed = MagicMock()
            completed.model_dump.return_value = {"type": "response.completed", "response": {}}
            completed.response = _fake_response()
            yield completed

        return _events()

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[LLMMessage(role="user", content="Question")],
        principal_id="user-1",
        history_mode="manual",
    )

    await adapter.infer_streaming_request(request=request)

    assert openai_client.responses.create.await_count == 2
    assert payloads[0]["input"][0]["content"] == "Question"


@pytest.mark.asyncio
async def test_infer_streaming_request_fails_when_stream_has_no_completed_response() -> None:
    async def _fake_create(**kwargs: Any) -> Any:
        del kwargs

        async def _events() -> AsyncGenerator:
            delta = MagicMock()
            delta.model_dump.return_value = {
                "type": "response.output_text.delta",
                "delta": "partial",
            }
            yield delta

        return _events()

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[LLMMessage(role="user", content="Question")],
        principal_id="user-1",
        history_mode="manual",
    )

    with pytest.raises(DomainValidationException) as raised:
        await adapter.infer_streaming_request(request=request)

    assert raised.value.errors() == ["stream_completed_without_response"]
    assert "Question" in str(raised.value.input_data)


@pytest.mark.asyncio
async def test_infer_streaming_request_strips_tool_headers_from_error_input_data() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=RuntimeError("boom"))
    adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
    request = OpenAIStreamingRequest(
        model_alias="gpt-4.1",
        input_messages=[
            LLMMessage(role="system", content="System"),
            LLMMessage(role="user", content="Sensitive user content"),
        ],
        principal_id="user-1",
        history_mode="manual",
        tools=[
            {
                "type": "mcp",
                "server_label": "tenant-mcp",
                "server_url": "https://mcp.example.com/mcp",
                "require_approval": "never",
                "headers": {"x-api-key": "top-secret", "authorization": "Bearer secret"},
            }
        ],
    )
    with pytest.raises(DomainValidationException) as raised:
        await adapter.infer_streaming_request(request=request)

    tool = raised.value.input_data["tools"][0]
    assert tool["server_url"] == "https://mcp.example.com/mcp"
    assert "headers" not in tool
    dump = str(raised.value.input_data)
    assert "Sensitive user content" in dump
    assert "top-secret" not in dump
    assert "Bearer secret" not in dump


def test_llm_domain_does_not_import_conversation() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "domain" / "llm"
    for file_path in root.rglob("*.py"):
        text = file_path.read_text(encoding="utf-8")
        assert "from domain.conversation" not in text
        assert "import domain.conversation" not in text
