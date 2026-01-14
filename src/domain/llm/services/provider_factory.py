from __future__ import annotations

from adapters.http.hardened_http_client import HardenedHttpClient
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.services.provider_selector import LLMProviderSelection
from domain.tools.ports.secret_resolver import SecretResolverPort


class LLMProviderFactory:
    def __init__(self, *, http_client: HardenedHttpClient, secret_resolver: SecretResolverPort) -> None:
        self.http_client = http_client
        self.secret_resolver = secret_resolver

    def build(self, selection: LLMProviderSelection) -> LLMProviderPort:
        if selection.provider.upper() == "OPENAI":
            return OpenAIProviderAdapter(
                http_client=self.http_client,
                secret_resolver=self.secret_resolver,
                base_url=selection.base_url or "https://api.openai.com/v1",
                credential_secret_ref=selection.credential_secret_ref,
            )
        raise ValueError(f"unsupported_provider:{selection.provider}")
