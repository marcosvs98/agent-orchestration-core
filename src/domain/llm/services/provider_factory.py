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
        ) as agent_handle:
            if selection.provider.upper() == LLMProviderType.OPENAI:
                provider: LLMProviderPort = OpenAIProviderAdapter(
                    secret_resolver=self.secret_resolver,
                    credential_secret_ref=selection.credential_secret_ref,
                    cache_adapter=self.cache_adapter,
                )
            if provider:
                if agent_handle:
                    agent_handle.success(
                        output={"provider": provider.__class__.__name__}
                    )
                return provider
            raise ValueError(f"unsupported_provider:{selection.provider}")
