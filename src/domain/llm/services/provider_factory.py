from __future__ import annotations

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMProviderType
from domain.llm.services.provider_selector import LLMProviderSelection


class LLMProviderFactory:
    def __init__(
        self,
        *,
        openai_provider: LLMProviderPort | None = None,
        slm_local_provider: LLMProviderPort | None = None,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.openai_provider = openai_provider
        self.slm_local_provider = slm_local_provider
        self.tracer = tracer

    def build(self, selection: LLMProviderSelection) -> LLMProviderPort:
        with self.tracer.observe(
            as_type="agent",
            name="domain.llm.provider_factory.build",
            input={"provider": selection.provider},
        ) as agent_handle:
            provider: LLMProviderPort | None = None
            if selection.provider.upper() == LLMProviderType.OPENAI:
                provider = self.openai_provider
            elif selection.provider.upper() == LLMProviderType.SLM_LOCAL:
                provider = self.slm_local_provider
            if provider is not None:
                if agent_handle:
                    agent_handle.success(output={"provider": provider.__class__.__name__})
                return provider
            raise ValueError(f"unsupported_provider:{selection.provider}")
