import json
from typing import Any, Dict, Optional, NewType, TYPE_CHECKING

from openai import AsyncOpenAI

from adapters.cache.redis_adapter import RedisAdapter
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

    async def _get_or_create_conversation_id(
        self, conversation_key: str
    ) -> ConversationId:
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
        cached = await self.cache_adapter.get(
            f"openai:previous_response:{conversation_key}"
        )
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

    async def infer(self, request: LLMRequest) -> LLMResult:
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
            "temperature": request.temperature
            if request.temperature is not None
            else 0.2,
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
            conversation_id = await self._get_or_create_conversation_id(
                request.conversation_key
            )
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

        try:
            response: Response = await self.openai_client.responses.create(
                **payload,
                service_tier="auto",
            )
        except Exception as exc:
            raise DomainValidationException(
                "llm_provider_error",
                input_data=payload,
                errors=[getattr(exc, "body", str(exc))],
            )

        if request.conversation_key and response.id:
            await self._set_previous_response_id(
                request.conversation_key,
                ConversationResponseID(response.id),
            )

        output_json: Dict[str, Any] | None = None
        output_text: Optional[str] = None

        if response.output:
            for block in response.output:
                for item in block.content or []:
                    if item.type == "output_json":
                        if isinstance(item.json, dict):
                            output_json = item.json
                    if item.type == "output_text":
                        output_text = item.text

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
            latency_ms=None,
            model_alias=request.model_alias,
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
                for item in block.content or []:
                    if item.type == "output_text":
                        output_text = item.text

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
