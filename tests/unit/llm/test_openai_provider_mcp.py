from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from adapters.mcp.conversation_mcp_context import (
    _CONVERSATION_MCP_CONFIG,
    set_conversation_mcp_config,
)
from domain.conversation.schemas.mcp_config import TenantMcpConfig
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.schemas.llm import LLMRequest
from exceptions.service_exceptions import DomainValidationException

_MCP_SERVER_ID = UUID("00000000-0000-0000-0000-000000001500")
_MCP_CONFIG = TenantMcpConfig(
    mcp_server_id=_MCP_SERVER_ID,
    mcp_server_url="https://mcp.example.com/core/v1/mcp-servers/00000000-0000-0000-0000-000000001500/mcp",
    mcp_access_key="mcp-key-123",
    outbound_api_key="outbound-key-456",
)


def _make_request(*, stream: bool = False) -> LLMRequest:
    return LLMRequest(
        model_alias="gpt-4o",
        prompt="Hello",
        stream=stream,
    )


def _fake_response() -> MagicMock:
    resp = MagicMock()
    resp.id = "resp-001"
    resp.output = []
    resp.usage = None
    resp.model_dump.return_value = {}
    return resp


def _make_adapter(captured_payloads: list[dict[str, Any]]) -> OpenAIProviderAdapter:
    async def _fake_create(**kwargs: Any) -> Any:
        captured_payloads.append(dict(kwargs))
        return _fake_response()

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    openai_client = MagicMock()
    openai_client.responses.create = AsyncMock(side_effect=_fake_create)
    openai_client.conversations.create = AsyncMock(return_value=MagicMock(id="conv-1"))

    return OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)


class TestOpenAIProviderMcpTools:
    @pytest.mark.asyncio
    async def test_no_tools_when_contextvar_not_set_and_not_streaming(self) -> None:
        payloads: list[dict] = []
        adapter = _make_adapter(payloads)
        await adapter.infer(_make_request(stream=False))
        assert "tools" not in payloads[0]

    @pytest.mark.asyncio
    async def test_no_tools_when_contextvar_not_set_streaming(self) -> None:
        payloads: list[dict] = []

        async def _fake_create_stream(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))

            async def _empty() -> AsyncGenerator:
                return
                yield  # make it an async generator

            return _empty()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create_stream)

        adapter2 = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
        on_delta = AsyncMock()

        tok = set_conversation_mcp_config(None)
        try:
            with pytest.raises(Exception):
                await adapter2.infer(_make_request(stream=True), on_delta=on_delta)
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)

        assert "tools" not in payloads[0]

    @pytest.mark.asyncio
    async def test_tools_injected_when_contextvar_set_and_streaming(self) -> None:
        payloads: list[dict] = []

        async def _fake_create_stream(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))

            async def _events() -> AsyncGenerator[Any, None]:
                resp = MagicMock()
                resp.model_dump.return_value = {"type": "response.completed", "response": {}}
                resp.response = _fake_response()
                yield resp

            return _events()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create_stream)

        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
        on_delta = AsyncMock()

        tok = set_conversation_mcp_config(_MCP_CONFIG)
        try:
            await adapter.infer(_make_request(stream=True), on_delta=on_delta)
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)

        assert len(payloads) == 1
        tools = payloads[0].get("tools")
        assert tools is not None
        assert len(tools) == 1
        assert tools[0]["type"] == "mcp"
        assert tools[0]["server_url"] == _MCP_CONFIG.mcp_server_url

    @pytest.mark.asyncio
    async def test_authorization_header_format(self) -> None:
        payloads: list[dict] = []

        async def _fake_create_stream(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))

            async def _events() -> AsyncGenerator[Any, None]:
                resp = MagicMock()
                resp.model_dump.return_value = {"type": "response.completed", "response": {}}
                resp.response = _fake_response()
                yield resp

            return _events()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create_stream)

        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
        on_delta = AsyncMock()

        tok = set_conversation_mcp_config(_MCP_CONFIG)
        try:
            await adapter.infer(_make_request(stream=True), on_delta=on_delta)
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)

        tool = payloads[0]["tools"][0]
        headers = tool["headers"]
        assert headers["x-api-key"] == "mcp-key-123"
        assert headers["authorization"] == "Bearer outbound-key-456"

    @pytest.mark.asyncio
    async def test_require_approval_never(self) -> None:
        payloads: list[dict] = []

        async def _fake_create_stream(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))

            async def _events() -> AsyncGenerator[Any, None]:
                resp = MagicMock()
                resp.model_dump.return_value = {"type": "response.completed", "response": {}}
                resp.response = _fake_response()
                yield resp

            return _events()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create_stream)

        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
        on_delta = AsyncMock()

        tok = set_conversation_mcp_config(_MCP_CONFIG)
        try:
            await adapter.infer(_make_request(stream=True), on_delta=on_delta)
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)

        assert payloads[0]["tools"][0]["require_approval"] == "never"

    @pytest.mark.asyncio
    async def test_no_tools_when_stream_false_even_with_contextvar_set(self) -> None:
        payloads: list[dict] = []
        adapter = _make_adapter(payloads)

        tok = set_conversation_mcp_config(_MCP_CONFIG)
        try:
            await adapter.infer(_make_request(stream=False))
        finally:
            _CONVERSATION_MCP_CONFIG.reset(tok)

        assert "tools" not in payloads[0]

    @pytest.mark.asyncio
    async def test_infer_conversation_stream_forwards_events_and_tools(self) -> None:
        payloads: list[dict] = []

        async def _fake_create(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))
            if kwargs.get("stream"):

                async def _events() -> AsyncGenerator[Any, None]:
                    delta = MagicMock()
                    delta.model_dump.return_value = {
                        "type": "response.output_text.delta",
                        "delta": "oi",
                    }
                    yield delta
                    completed = MagicMock()
                    completed.model_dump.return_value = {
                        "type": "response.completed",
                        "response": {},
                    }
                    completed.response = _fake_response()
                    yield completed

                return _events()
            return _fake_response()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create)
        openai_client.conversations.create = AsyncMock(return_value=MagicMock(id="conv-1"))
        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)
        events: list[str] = []

        async def _on_event(evt: dict[str, Any]) -> None:
            events.append(str(evt.get("type", "")))

        tools = [
            {
                "type": "mcp",
                "server_label": "tenant-mcp",
                "server_url": _MCP_CONFIG.mcp_server_url,
                "require_approval": "never",
                "headers": {"x-api-key": "x", "authorization": "Bearer y"},
            }
        ]
        await adapter.infer_conversation_stream(
            model="gpt-4.1",
            instructions="i",
            user_input="u",
            conversation_key="tenant:session",
            mcp_tools=tools,
            on_openai_event=_on_event,
        )
        assert events == ["response.output_text.delta", "response.completed"]
        assert payloads[0]["tools"][0]["server_url"] == _MCP_CONFIG.mcp_server_url

    @pytest.mark.asyncio
    async def test_infer_conversation_stream_uses_message_history_input(self) -> None:
        payloads: list[dict] = []

        async def _fake_create(**kwargs: Any) -> Any:
            payloads.append(dict(kwargs))
            if kwargs.get("stream"):

                async def _events() -> AsyncGenerator[Any, None]:
                    completed = MagicMock()
                    completed.model_dump.return_value = {
                        "type": "response.completed",
                        "response": {},
                    }
                    completed.response = _fake_response()
                    yield completed

                return _events()
            return _fake_response()

        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(side_effect=_fake_create)
        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)

        await adapter.infer_conversation_stream(
            model="gpt-4.1",
            instructions="i",
            user_input="Preciso de detalhes da fatura",
            message_history=[
                {"role": "user", "content": "Cartão e fatura"},
                {"role": "assistant", "content": "Escolha o cartão VISA INFINITE"},
            ],
        )

        assert payloads[0]["input"] == [
            {"role": "system", "content": "i"},
            {"role": "user", "content": "Cartão e fatura"},
            {"role": "assistant", "content": "Escolha o cartão VISA INFINITE"},
            {"role": "user", "content": "Preciso de detalhes da fatura"},
        ]
        assert "conversation" not in payloads[0]

    @pytest.mark.asyncio
    async def test_infer_conversation_stream_wraps_provider_error_with_details(self) -> None:
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        openai_client = MagicMock()
        openai_client.responses.create = AsyncMock(
            side_effect=RuntimeError("Error code: 424 - Failed Dependency")
        )
        openai_client.conversations.create = AsyncMock(return_value=MagicMock(id="conv-1"))
        adapter = OpenAIProviderAdapter(cache_adapter=cache, openai_client=openai_client)

        with pytest.raises(DomainValidationException) as raised:
            await adapter.infer_conversation_stream(
                model="gpt-4.1",
                instructions="i",
                user_input="u",
            )

        assert raised.value.message == "llm_provider_error"
        assert raised.value.errors() == ["provider_failed_dependency"]
