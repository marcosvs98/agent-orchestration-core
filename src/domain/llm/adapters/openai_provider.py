from __future__ import annotations

from typing import Any, Dict

from adapters.http.hardened_http_client import HardenedHttpClient
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult
from domain.tools.ports.secret_resolver import SecretResolverPort
from exceptions.service_exceptions import DomainValidationException


class OpenAIProviderAdapter(LLMProviderPort):
    def __init__(
        self,
        *,
        http_client: HardenedHttpClient,
        secret_resolver: SecretResolverPort,
        base_url: str = "https://api.openai.com/v1",
        credential_secret_ref: str | None = None,
    ) -> None:
        self.http_client = http_client
        self.secret_resolver = secret_resolver
        self.base_url = base_url.rstrip("/")
        self.credential_secret_ref = credential_secret_ref

    async def _headers(self) -> Dict[str, str]:
        if not self.credential_secret_ref:
            raise DomainValidationException(message="llm_provider_missing_credentials")
        api_key = await self.secret_resolver.resolve(secret_ref=self.credential_secret_ref)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def infer(self, request: LLMRequest) -> LLMResult:
        headers = await self._headers()
        url = f"{self.base_url}/chat/completions"
        body: Dict[str, Any] = {
            "model": request.model_alias,
            "messages": [
                {
                    "role": "user",
                    "content": request.input_payload.get("prompt") or str(request.input_payload),
                }
            ],
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens

        response = await self.http_client.post_json(
            url=url,
            headers=headers,
            json_body=body,
            timeout_seconds=(request.max_latency_ms / 1000) if request.max_latency_ms else None,
        )

        if response.status_code >= 400:
            raise DomainValidationException(
                message="llm_provider_error",
                detail=f"status={response.status_code}",
            )

        data = response.json()
        choices = data.get("choices") or []
        content = None
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")

        usage = data.get("usage") or {}
        token_usage = {
            "input_tokens": usage.get("prompt_tokens", 0) or 0,
            "output_tokens": usage.get("completion_tokens", 0) or 0,
        }
        return LLMResult(
            output={"content": content},
            token_usage=token_usage,
            cost_usd=None,
            latency_ms=None,
            model_alias=request.model_alias,
        )
