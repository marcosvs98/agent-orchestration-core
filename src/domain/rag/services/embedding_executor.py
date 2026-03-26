from __future__ import annotations

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.schemas.embedding import (
    EmbeddingBatchExecutionRequest,
    EmbeddingExecutionRequest,
)
from domain.rag.services.embedding_adapter_factory import EmbeddingProviderFactory
from domain.rag.services.embedding_provider_selector import EmbeddingProviderSelector
from exceptions.service_exceptions import DomainValidationException


class EmbeddingExecutor:
    def __init__(
        self,
        *,
        selector: EmbeddingProviderSelector,
        factory: EmbeddingProviderFactory,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.selector = selector
        self.factory = factory
        self.tracer = tracer

    async def execute(self, request: EmbeddingExecutionRequest) -> list[float]:
        with self.tracer.observe(
            as_type="embedding",
            name="domain.rag.embedding_executor.execute",
            input={
                "use_case": request.use_case,
                "model": request.contract.model,
                "dimension": request.contract.dimension,
                "version": request.contract.version,
            },
        ) as embedding_handle:
            selection = await self.selector.select(contract=request.contract)
            provider = self.factory.build(selection)
            embedding = await provider.generate_embedding(
                request.text,
                model=selection.provider_model,
                dimension=request.contract.dimension,
            )
            if len(embedding) == request.contract.dimension:
                if embedding_handle:
                    pass  # Todo:
                return embedding
            raise DomainValidationException(message="rag_embedding_dimension_mismatch")

    async def execute_batch(
        self, request: EmbeddingBatchExecutionRequest
    ) -> list[list[float]]:
        with self.tracer.observe(
            as_type="embedding",
            name="domain.rag.embedding_executor.execute_batch",
            input={
                "use_case": request.use_case,
                "model": request.contract.model,
                "dimension": request.contract.dimension,
                "version": request.contract.version,
                "size": len(request.texts),
            },
        ):
            selection = await self.selector.select(contract=request.contract)
            provider = self.factory.build(selection)
            embeddings = await provider.generate_embeddings_batch(
                request.texts,
                model=selection.provider_model,
                dimension=request.contract.dimension,
            )
            for embedding in embeddings:
                if len(embedding) != request.contract.dimension:
                    raise DomainValidationException(
                        message="rag_embedding_dimension_mismatch"
                    )
            return embeddings
