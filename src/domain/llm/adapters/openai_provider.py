import orjson
from typing import Any, Dict, Optional, NewType

from adapters.http.hardened_http_client import HardenedHttpClient
from adapters.cache.redis_adapter import RedisAdapter
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.tools.ports.secret_resolver import SecretResolverPort
from exceptions.service_exceptions import DomainValidationException

from domain.llm.schemas.llm import LLMRequest, LLMResult

ConversationId = NewType("ConversationId", str)
ConversationResponseID = NewType("ConversationResponseID", str)


class OpenAIProviderAdapter(LLMProviderPort):
    CONVERSATION_TTL_SECONDS = 60 * 60 * 24

    def __init__(
        self,
        *,
        http_client: HardenedHttpClient,
        secret_resolver: SecretResolverPort,
        cache_adapter: RedisAdapter,
        base_url: str = "https://api.openai.com/v1",
        credential_secret_ref: str | None = None,
    ) -> None:
        self.http_client = http_client
        self.secret_resolver = secret_resolver
        self.cache_adapter = cache_adapter
        self.base_url = base_url.rstrip("/")
        self.credential_secret_ref = credential_secret_ref

    async def _headers(self) -> Dict[str, str]:
        if not self.credential_secret_ref:
            raise DomainValidationException("llm_provider_missing_credentials")

        api_key = await self.secret_resolver.resolve(
            secret_ref=self.credential_secret_ref
        )
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _get_or_create_conversation_id(
        self, conversation_key: str
    ) -> ConversationId:
        cache_key = f"openai:conversation:{conversation_key}"

        cached = await self.cache_adapter.get(cache_key)
        if cached:
            return ConversationId(cached)

        response = await self.http_client.post_json(
            url=f"{self.base_url}/conversations",
            headers=await self._headers(),
            json_body={},
        )

        if response.status_code >= 400:
            raise DomainValidationException("conversation_creation_failed")

        conversation_id = response.json().get("id")
        if not conversation_id:
            raise DomainValidationException("invalid_conversation_response")

        typed_id = ConversationId(conversation_id)

        await self.cache_adapter.set(
            cache_key,
            typed_id,
            ttl_seconds=self.CONVERSATION_TTL_SECONDS,
        )
        return typed_id

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
            ttl_seconds=self.CONVERSATION_TTL_SECONDS,
        )

    async def infer(self, request: LLMRequest) -> LLMResult:
        headers = await self._headers()
        url = f"{self.base_url}/responses"

        body: Dict[str, Any] = {
            "model": request.model_alias,
            "input": request.prompt,
            "text": {"format": {"type": "json_object"}},
        }

        if request.system_prompt:
            body["system"] = request.system_prompt

        if request.max_tokens is not None:
            body["max_output_tokens"] = request.max_tokens

        conversation_key = request.conversation_key
        stateless = request.stateless

        if conversation_key:
            conversation_id = await self._get_or_create_conversation_id(
                conversation_key
            )

            if stateless:
                body["conversation"] = conversation_id
            else:
                previous_response_id = await self._get_previous_response_id(
                    conversation_key
                )
                if previous_response_id:
                    body["previous_response_id"] = previous_response_id
                else:
                    body["conversation"] = conversation_id

        timeout = request.max_latency_ms / 1000 if request.max_latency_ms else None

        response = await self.http_client.post_json(
            url=url,
            headers=headers,
            json_body=body,
            timeout_seconds=timeout,
        )

        if response.status_code >= 400:
            raise DomainValidationException(
                "llm_provider_error",
                detail=f"status={response.status_code}",
            )

        raw_output = response.json()

        response_id = raw_output.get("id")
        if conversation_key and response_id:
            await self._set_previous_response_id(
                conversation_key,
                ConversationResponseID(response_id),
            )

        output_text = ""
        output_blocks = raw_output.get("output") or []
        if output_blocks:
            content = output_blocks[0].get("content") or []
            if content:
                output_text = content[0].get("text", "") or "{}"

        usage_raw = raw_output.get("usage") or {}
        token_usage = {
            "input_tokens": usage_raw.get("input_tokens", 0),
            "output_tokens": usage_raw.get("output_tokens", 0),
            "cached_input_tokens": (
                usage_raw.get("input_tokens_details", {}).get("cached_tokens", 0)
            ),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

        return LLMResult(
            output={"content": output_text},
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=None,
            model_alias=request.model_alias,
            raw_output=raw_output,
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
        headers = await self._headers()
        url = f"{self.base_url}/chat/completions"

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.http_client.post_json(
            url=url,
            headers=headers,
            json_body=body,
            prompt_cache_key=cache_key,
        )

        if response.status_code >= 400:
            raise DomainValidationException("llm_classification_failed")

        raw_output = response.json()
        choices = raw_output.get("choices") or []

        output: Dict[str, Any] = {}
        if choices:
            message = choices[0].get("message") or {}
            try:
                output = orjson.loads(message.get("content") or "{}")
            except Exception:
                output = {}

        usage_raw = raw_output.get("usage") or {}
        token_usage = {
            "input_tokens": usage_raw.get("prompt_tokens", 0),
            "output_tokens": usage_raw.get("completion_tokens", 0),
            "cached_input_tokens": (
                usage_raw.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            ),
        }
        return LLMResult(
            output=output,
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=None,
            model_alias=model,
            raw_output=raw_output,
        )
