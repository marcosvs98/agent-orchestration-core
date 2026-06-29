import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional, NewType, TYPE_CHECKING

from openai import AsyncOpenAI

from adapters.cache.redis_adapter import RedisAdapter
from adapters.mcp.conversation_mcp_context import get_conversation_mcp_config
from domain.llm.ports.llm_provider import LLMProviderPort
from exceptions.service_exceptions import DomainValidationException
from domain.llm.schemas.llm import LLMRequest, LLMResult

if TYPE_CHECKING:
    from openai.types.responses import Response
    from openai.types.conversations import Conversation
    from openai.types.responses.response_usage import ResponseUsage


ConversationId = NewType("ConversationId", str)
ConversationResponseID = NewType("ConversationResponseID", str)


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
        try:
            start = time.perf_counter()
            if request.stream and on_delta is not None:
                stream = await self.openai_client.responses.create(
                    **payload,
                    stream=True,
                    service_tier="auto",
                )
                async for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "") or ""
                        if delta:
                            accumulated_text += delta
                            await on_delta(delta)
                    elif event_type == "response.completed":
                        response = event.response
            else:
                response = await self.openai_client.responses.create(
                    **payload,
                    service_tier="auto",
                )
        except Exception as exc:
            raise DomainValidationException(
                "llm_provider_error",
                input_data=payload,
                errors=[str(exc)],
            )
        else:
            latency_ms = (time.perf_counter() - start) * 1000

        if response is None:
            raise DomainValidationException(
                "llm_provider_error",
                input_data=payload,
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
                block_payload = (
                    block.model_dump(mode="json")
                    if hasattr(block, "model_dump")
                    else {}
                )
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
        on_openai_event: Callable[[Any], Awaitable[None]] | None = None,
    ) -> LLMResult:
        payload: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "temperature": temperature,
            "store": store,
        }
        if user_id:
            payload["user"] = user_id
        if message_history:
            payload["input"] = [
                *message_history,
                {"role": "user", "content": user_input},
            ]
        else:
            payload["input"] = user_input
            if conversation_key:
                conversation_id = await self._get_or_create_conversation_id(conversation_key)
                # store=False (default) does not persist responses; previous_response_id
                # fails on follow-up turns. Use OpenAI conversation for multi-turn instead.
                if store:
                    previous_response_id = await self._get_previous_response_id(conversation_key)
                    if previous_response_id:
                        payload["previous_response_id"] = previous_response_id
                    else:
                        payload["conversation"] = conversation_id
                else:
                    payload["conversation"] = conversation_id
        if mcp_tools:
            payload["tools"] = mcp_tools

        response: Response | None = None
        accumulated_text = ""
        start = time.perf_counter()
        try:
            try:
                stream = await self.openai_client.responses.create(
                    **payload,
                    stream=True,
                    service_tier="auto",
                )
                async for event in stream:
                    if on_openai_event is not None:
                        await on_openai_event(event)
                    event_payload = (
                        event.model_dump(mode="json")
                        if hasattr(event, "model_dump")
                        else {}
                    )
                    event_type = event_payload.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event_payload.get("delta", "") or ""
                        if delta:
                            accumulated_text += str(delta)
                    elif event_type == "response.completed":
                        response_data = event_payload.get("response")
                        if isinstance(response_data, dict):
                            response = event.response
            except Exception as exc:
                err_text = str(exc)
                if "424" not in err_text and "Failed Dependency" not in err_text:
                    raise
                stream = await self.openai_client.responses.create(
                    **payload,
                    stream=True,
                    service_tier="auto",
                )
                async for event in stream:
                    if on_openai_event is not None:
                        await on_openai_event(event)
                    event_payload = (
                        event.model_dump(mode="json")
                        if hasattr(event, "model_dump")
                        else {}
                    )
                    event_type = event_payload.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event_payload.get("delta", "") or ""
                        if delta:
                            accumulated_text += str(delta)
                    elif event_type == "response.completed":
                        response_data = event_payload.get("response")
                        if isinstance(response_data, dict):
                            response = event.response
        except Exception as exc:
            raise DomainValidationException(
                "llm_provider_error",
                input_data=payload,
                errors=[str(exc)],
            ) from exc

        latency_ms = (time.perf_counter() - start) * 1000
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
                model_alias=model,
                raw_output={},
            )

        if conversation_key and response.id and not message_history:
            await self._set_previous_response_id(
                conversation_key,
                ConversationResponseID(response.id),
            )

        output_text: Optional[str] = None
        output_json: Dict[str, Any] | None = None
        if response.output:
            for block in response.output:
                block_payload = (
                    block.model_dump(mode="json")
                    if hasattr(block, "model_dump")
                    else {}
                )
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
            model_alias=model,
            raw_output=response.model_dump(),
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
            )

        output_text = ""
        if response.output:
            for block in response.output:
                block_payload = (
                    block.model_dump(mode="json")
                    if hasattr(block, "model_dump")
                    else {}
                )
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
