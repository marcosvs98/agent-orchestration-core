from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional, NewType, TYPE_CHECKING

from openai import AsyncOpenAI

from adapters.cache.redis_adapter import RedisAdapter
from adapters.mcp.conversation_mcp_context import get_conversation_mcp_config
from adapters.observability.logging import get_logger
from domain.llm.ports.llm_provider import LLMProviderPort
from exceptions.service_exceptions import DomainValidationException
from domain.llm.schemas.llm import LLMRequest, LLMResult
from domain.llm.schemas.openai_streaming import OpenAIStreamingRequest

if TYPE_CHECKING:
    from openai.types.responses import Response
    from openai.types.conversations import Conversation
    from openai.types.responses.response_usage import ResponseUsage


ConversationId = NewType("ConversationId", str)
ConversationResponseID = NewType("ConversationResponseID", str)

logger = get_logger(__name__)


class OpenAIProviderAdapter(LLMProviderPort):
    CONVERSATION_TTL_SECONDS = 60 * 60 * 24

    def __init__(
        self,
        *,
        cache_adapter: RedisAdapter,
        openai_client: AsyncOpenAI,
    ) -> None:
        self.cache_adapter: RedisAdapter = cache_adapter
        self.openai_client: AsyncOpenAI = openai_client

    async def _get_or_create_conversation_id(self, conversation_key: str) -> ConversationId:
        cache_key = f"openai:conversation:{conversation_key}"

        cached = await self.cache_adapter.get(cache_key)
        if cached:
            return ConversationId(cached)

        conversation: Conversation = await self.openai_client.conversations.create(
            metadata={"conversation_key": conversation_key}
        )

        conversation_id = ConversationId(conversation.id)

        await self.cache_adapter.set(
            cache_key,
            conversation_id,
            ttl=self.CONVERSATION_TTL_SECONDS,
        )
        return conversation_id

    async def _get_previous_response_id(
        self, conversation_key: str
    ) -> Optional[ConversationResponseID]:
        cached = await self.cache_adapter.get(f"openai:previous_response:{conversation_key}")
        return ConversationResponseID(cached) if cached else None

    async def _set_previous_response_id(
        self,
        conversation_key: str,
        response_id: ConversationResponseID,
    ) -> None:
        await self.cache_adapter.set(
            f"openai:previous_response:{conversation_key}",
            response_id,
            ttl=self.CONVERSATION_TTL_SECONDS,
        )

    async def infer(
        self,
        request: LLMRequest,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResult:
        messages: list[dict[str, str]] = [
            message.model_dump(mode="json") for message in request.messages
        ]
        if not messages:
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            if request.system_context:
                messages.append({"role": "system", "content": request.system_context})
            if request.prompt:
                messages.append({"role": "system", "content": request.prompt})
            if request.user_message:
                messages.append({"role": "user", "content": request.user_message})

        schema_payload = request.json_schema or request.output_schema or {}
        payload: Dict[str, Any] = {
            "model": request.model_alias,
            "input": messages if messages else request.prompt,
            "temperature": request.temperature if request.temperature is not None else 0.2,
        }

        if schema_payload:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.json_schema_name
                    or (
                        f"{request.task_type.value.lower()}_output"
                        if request.task_type
                        else "llm_output"
                    ),
                    "schema": schema_payload,
                }
            }
        else:
            payload["text"] = {"format": {"type": request.text_format or "json_object"}}

        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens

        if request.prompt_cache_key:
            payload["prompt_cache_key"] = request.prompt_cache_key
            payload["prompt_cache_retention"] = "24h"

        if request.metadata:
            payload["metadata"] = request.metadata

        if request.user_id:
            payload["user"] = request.user_id

        if request.conversation_key:
            conversation_id = await self._get_or_create_conversation_id(request.conversation_key)
            previous_response_id: Optional[ConversationResponseID] = None
            if request.stateless:
                payload["conversation"] = conversation_id
            else:
                previous_response_id = await self._get_previous_response_id(
                    request.conversation_key
                )
                if previous_response_id:
                    payload["previous_response_id"] = previous_response_id
                else:
                    payload["conversation"] = conversation_id

        if request.stream and on_delta is not None:
            mcp_cfg = get_conversation_mcp_config()
            if mcp_cfg is not None:
                payload["tools"] = [
                    {
                        "type": "mcp",
                        "server_label": "tenant-mcp",
                        "server_url": mcp_cfg.mcp_server_url,
                        "require_approval": "never",
                        "headers": {
                            "x-api-key": mcp_cfg.mcp_access_key,
                            "authorization": f"Bearer {mcp_cfg.outbound_api_key}",
                        },
                    }
                ]

        response: Response | None = None
        output_text: Optional[str] = None
        accumulated_text = ""
        start = time.perf_counter()
        try:
            if request.stream and on_delta is not None:
                stream = await self.openai_client.responses.create(
                    **payload,
                    stream=True,
                    service_tier="auto",
                )
                async for event in stream:
                    event_payload = event.model_dump(mode="json")
                    event_type = event_payload.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event_payload.get("delta", "") or ""
                        if delta:
                            accumulated_text += delta
                            await on_delta(delta)
                    elif event_type == "response.completed":
                        response_data = event_payload.get("response")
                        if isinstance(response_data, dict):
                            response = event.response
            else:
                response = await self.openai_client.responses.create(
                    **payload,
                    service_tier="auto",
                )
        except Exception as exc:
            provider_error = self._sanitize_provider_error(exc)
            logger.exception(
                "openai_infer_failed",
                model=payload.get("model"),
                has_mcp_tools=bool(payload.get("tools")),
                has_message_history=isinstance(payload.get("input"), list),
                error_type=type(exc).__name__,
                provider_error=provider_error,
            )
            raise DomainValidationException(
                "llm_provider_error",
                input_data={
                    **payload,
                    "tools": [
                        {key: value for key, value in tool.items() if key != "headers"}
                        if isinstance(tool, dict)
                        else tool
                        for tool in payload.get("tools", [])
                    ]
                    if isinstance(payload.get("tools"), list)
                    else payload.get("tools"),
                },
                errors=[provider_error],
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000

        if response is None:
            raise DomainValidationException(
                "llm_provider_error",
                input_data={
                    **payload,
                    "tools": [
                        {key: value for key, value in tool.items() if key != "headers"}
                        if isinstance(tool, dict)
                        else tool
                        for tool in payload.get("tools", [])
                    ]
                    if isinstance(payload.get("tools"), list)
                    else payload.get("tools"),
                },
                errors=["stream_completed_without_response"],
            )

        if request.conversation_key and response.id:
            await self._set_previous_response_id(
                request.conversation_key,
                ConversationResponseID(response.id),
            )

        output_json: Dict[str, Any] | None = None
        if response.output:
            for block in response.output:
                block_payload = block.model_dump(mode="json")
                content_items = block_payload.get("content", [])
                if not isinstance(content_items, list):
                    continue
                for item in content_items:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("type")
                    if item_type == "output_json" and isinstance(item.get("json"), dict):
                        output_json = item["json"]
                    if item_type == "output_text" and isinstance(item.get("text"), str):
                        output_text = item["text"]
        if output_text is None and accumulated_text:
            output_text = accumulated_text

        if output_json is None and output_text:
            try:
                parsed_output = json.loads(output_text)
                if isinstance(parsed_output, dict):
                    output_json = parsed_output
            except json.JSONDecodeError:
                output_json = None

        usage: ResponseUsage | None = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        cached_tokens = 0
        if usage and usage.input_tokens_details:
            cached_tokens = usage.input_tokens_details.cached_tokens or 0
        token_usage = {
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "cached_input_tokens": cached_tokens,
            "total_tokens": total_tokens or 0,
        }

        return LLMResult(
            output=output_json if output_json is not None else {"content": output_text},
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=latency_ms,
            model_alias=request.model_alias,
            raw_output=response.model_dump(),
        )

    async def _compile_streaming_payload(
        self,
        request: OpenAIStreamingRequest,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model_alias,
            "input": [message.model_dump(mode="json") for message in request.input_messages],
            "temperature": request.temperature,
            "store": False,
        }
        if request.principal_id:
            payload["user"] = request.principal_id
        if request.tools:
            payload["tools"] = request.tools
        if request.history_mode == "provider_conversation" and request.conversation_key:
            conversation_id = await self._get_or_create_conversation_id(request.conversation_key)
            payload["conversation"] = conversation_id
        return payload

    async def _consume_response_stream(
        self,
        payload: dict[str, Any],
        on_openai_event: Callable[[dict[str, Any]], Awaitable[None]] | None,
        allow_retry: bool,
    ) -> tuple[Response | None, str]:
        response: Response | None = None
        accumulated_text = ""
        attempts = 2 if allow_retry else 1
        for attempt in range(attempts):
            try:
                stream = await self.openai_client.responses.create(
                    **payload,
                    stream=True,
                    service_tier="auto",
                )
                async for event in stream:
                    event_payload = event.model_dump(mode="json")
                    if on_openai_event is not None:
                        await on_openai_event(event_payload)
                    event_type = event_payload.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event_payload.get("delta", "") or ""
                        if delta:
                            accumulated_text += str(delta)
                    elif event_type == "response.completed":
                        response_data = event_payload.get("response")
                        if isinstance(response_data, dict):
                            response = event.response
                return response, accumulated_text
            except Exception as exc:
                is_retryable = "424" in str(exc) or "Failed Dependency" in str(exc)
                if not allow_retry or attempt == attempts - 1 or not is_retryable:
                    raise
        return response, accumulated_text

    def _build_stream_result(
        self,
        model_alias: str,
        response: Response | None,
        accumulated_text: str,
        latency_ms: float,
    ) -> LLMResult:
        if response is None:
            return LLMResult(
                output={"content": accumulated_text},
                token_usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cached_input_tokens": 0,
                    "total_tokens": 0,
                },
                cost_usd=None,
                latency_ms=latency_ms,
                model_alias=model_alias,
                raw_output={},
            )

        output_text: Optional[str] = None
        output_json: Dict[str, Any] | None = None
        if response.output:
            for block in response.output:
                block_payload = block.model_dump(mode="json")
                content_items = block_payload.get("content", [])
                if not isinstance(content_items, list):
                    continue
                for item in content_items:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("type")
                    if item_type == "output_json" and isinstance(item.get("json"), dict):
                        output_json = item["json"]
                    if item_type == "output_text" and isinstance(item.get("text"), str):
                        output_text = item["text"]

        if output_text is None and accumulated_text:
            output_text = accumulated_text
        if output_json is None and output_text:
            try:
                parsed_output = json.loads(output_text)
                if isinstance(parsed_output, dict):
                    output_json = parsed_output
            except json.JSONDecodeError:
                output_json = None

        usage: ResponseUsage | None = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        cached_tokens = 0
        if usage and usage.input_tokens_details:
            cached_tokens = usage.input_tokens_details.cached_tokens or 0
        token_usage = {
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "cached_input_tokens": cached_tokens,
            "total_tokens": total_tokens or 0,
        }

        return LLMResult(
            output=output_json if output_json is not None else {"content": output_text},
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=latency_ms,
            model_alias=model_alias,
            raw_output=response.model_dump(),
        )

    def _sanitize_provider_error(self, exc: Exception) -> str:
        error_text = str(exc)
        if "424" in error_text or "Failed Dependency" in error_text:
            return "provider_failed_dependency"
        return type(exc).__name__

    async def infer_streaming_request(
        self,
        request: OpenAIStreamingRequest,
        on_openai_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> LLMResult:
        payload = await self._compile_streaming_payload(request)
        allow_retry = not bool(request.tools)
        start = time.perf_counter()
        try:
            response, accumulated_text = await self._consume_response_stream(
                payload=payload,
                on_openai_event=on_openai_event,
                allow_retry=allow_retry,
            )
        except Exception as exc:
            provider_error = self._sanitize_provider_error(exc)
            logger.exception(
                "openai_infer_conversation_stream_failed",
                model=payload.get("model"),
                has_mcp_tools=bool(payload.get("tools")),
                has_message_history=isinstance(payload.get("input"), list),
                error_type=type(exc).__name__,
                provider_error=provider_error,
            )
            raise DomainValidationException(
                "llm_provider_error",
                input_data={
                    **payload,
                    "tools": [
                        {key: value for key, value in tool.items() if key != "headers"}
                        if isinstance(tool, dict)
                        else tool
                        for tool in payload.get("tools", [])
                    ]
                    if isinstance(payload.get("tools"), list)
                    else payload.get("tools"),
                },
                errors=[provider_error],
            ) from exc

        if response is None:
            raise DomainValidationException(
                "llm_provider_error",
                input_data={
                    **payload,
                    "tools": [
                        {key: value for key, value in tool.items() if key != "headers"}
                        if isinstance(tool, dict)
                        else tool
                        for tool in payload.get("tools", [])
                    ]
                    if isinstance(payload.get("tools"), list)
                    else payload.get("tools"),
                },
                errors=["stream_completed_without_response"],
            )

        latency_ms = (time.perf_counter() - start) * 1000
        if (
            request.history_mode == "provider_conversation"
            and request.conversation_key
            and response is not None
            and response.id
        ):
            await self._set_previous_response_id(
                request.conversation_key,
                ConversationResponseID(response.id),
            )
        return self._build_stream_result(
            model_alias=request.model_alias,
            response=response,
            accumulated_text=accumulated_text,
            latency_ms=latency_ms,
        )

    async def infer_conversation_stream(
        self,
        *,
        model: str,
        instructions: str,
        user_input: str,
        temperature: float = 0.2,
        user_id: str | None = None,
        conversation_key: str | None = None,
        message_history: list[dict[str, str]] | None = None,
        mcp_tools: list[dict[str, Any]] | None = None,
        store: bool = False,
        on_openai_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> LLMResult:
        del store
        input_messages: list[dict[str, str]] = []
        normalized_instructions = instructions.strip()
        if normalized_instructions:
            input_messages.append({"role": "system", "content": normalized_instructions})
        if message_history:
            for item in message_history:
                role = item.get("role", "")
                content = item.get("content", "")
                if role in {"user", "assistant"} and content:
                    input_messages.append({"role": role, "content": content})
        input_messages.append({"role": "user", "content": user_input})
        history_mode = (
            "provider_conversation"
            if not message_history and conversation_key is not None
            else "manual"
        )
        streaming_request = OpenAIStreamingRequest(
            model_alias=model,
            input_messages=input_messages,
            principal_id=user_id,
            conversation_key=conversation_key if history_mode == "provider_conversation" else None,
            history_mode=history_mode,
            tools=mcp_tools or [],
            temperature=temperature,
        )
        return await self.infer_streaming_request(
            request=streaming_request,
            on_openai_event=on_openai_event,
        )

    async def classify(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        cache_key: Optional[str] = None,
        max_tokens: int = 300,
        temperature: float = 0.0,
    ) -> LLMResult:
        payload = {
            "model": model,
            "input": user_message,
            "instructions": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "text": {"format": {"type": "text"}},
        }

        if cache_key:
            payload["prompt_cache_key"] = cache_key
            payload["prompt_cache_retention"] = "24h"

        try:
            response: Response = await self.openai_client.responses.create(**payload)
        except Exception as exc:
            raise DomainValidationException(
                "llm_classification_failed",
                detail=str(exc),
            ) from exc

        output_text = ""
        if response.output:
            for block in response.output:
                block_payload = block.model_dump(mode="json")
                content_items = block_payload.get("content", [])
                if not isinstance(content_items, list):
                    continue
                for item in content_items:
                    if isinstance(item, dict) and item.get("type") == "output_text":
                        text = item.get("text")
                        if isinstance(text, str):
                            output_text = text

        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        cached_tokens = 0
        if usage and usage.input_tokens_details:
            cached_tokens = usage.input_tokens_details.cached_tokens or 0
        token_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_tokens,
        }

        return LLMResult(
            output={"content": output_text},
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=None,
            model_alias=model,
            raw_output=response.model_dump(),
        )
