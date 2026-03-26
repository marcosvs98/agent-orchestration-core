from __future__ import annotations

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.ports.embedding import EmbeddingPort
from domain.rag.schemas.embedding import EmbeddingProviderSelection
from exceptions.service_exceptions import DomainValidationException


class EmbeddingProviderFactory:
    def __init__(
        self,
        *,
        tracer: RuntimeTracerPort,
        embedding_adapter: EmbeddingPort,
    ) -> None:
        self.tracer = tracer
        self.embedding_adapter = embedding_adapter

    def build(self, selection: EmbeddingProviderSelection) -> EmbeddingPort:
        with self.tracer.observe(
            as_type="agent",
            name="domain.rag.embedding_provider_factory.build",
            input={"provider": selection.provider},
        ):
            if selection.provider.lower() == "openai":  # Todo: StrEnum here
                return self.embedding_adapter
        raise DomainValidationException(message="embedding_provider_not_supported")
