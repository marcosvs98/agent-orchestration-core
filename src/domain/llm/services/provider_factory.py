from __future__ import annotations


from adapters.cache.redis_adapter import RedisAdapter
from adapters.http.hardened_http_client import HardenedHttpClient
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.llm.adapters.openai_provider import OpenAIProviderAdapter
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMProviderType
from domain.llm.services.provider_selector import LLMProviderSelection
from domain.tools.ports.secret_resolver import SecretResolverPort


class LLMProviderFactory:
    def __init__(
        self,
        *,
        http_client: HardenedHttpClient,
        secret_resolver: SecretResolverPort,
        cache_adapter: RedisAdapter,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.http_client = http_client
        self.secret_resolver = secret_resolver
        self.cache_adapter = cache_adapter
        self.tracer = tracer

    def build(self, selection: LLMProviderSelection) -> LLMProviderPort:
        with self.tracer.observe(
            as_type="agent",
            name="domain.llm.provider_factory.build",
            input={"provider": selection.provider},
        ):
            if selection.provider.upper() == LLMProviderType.OPENAI:
                return OpenAIProviderAdapter(
                    http_client=self.http_client,
                    secret_resolver=self.secret_resolver,
                    base_url=selection.base_url or "https://api.openai.com/v1",
                    credential_secret_ref=selection.credential_secret_ref,
                    cache_adapter=self.cache_adapter,
                )
            raise ValueError(f"unsupported_provider:{selection.provider}")
