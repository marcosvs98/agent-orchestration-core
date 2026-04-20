from __future__ import annotations

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.schemas.embedding import (
    EmbeddingContract,
    EmbeddingProviderSelection,
)


class EmbeddingProviderSelector:
    def __init__(self, *, tracer: RuntimeTracerPort) -> None:
        self.tracer = tracer

    async def select(self, *, contract: EmbeddingContract) -> EmbeddingProviderSelection:
        with self.tracer.observe(
            as_type="agent",
            name="domain.rag.embedding_provider_selector.select",
            input={
                "provider": contract.provider,
                "model": contract.model,
                "dimension": contract.dimension,
                "version": contract.version,
            },
        ):
            return EmbeddingProviderSelection(
                provider=contract.provider,
                provider_model=contract.model,
                contract=contract,
            )
