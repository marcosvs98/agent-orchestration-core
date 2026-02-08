from __future__ import annotations

from typing import List

from openai import AsyncOpenAI

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from adapters.observability.logging import get_logger

logger = get_logger()


class OpenAIEmbeddingAdapter:
    """Generate embeddings using OpenAI."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = dimension
        self.tracer = tracer

    async def generate_embedding(
        self, text: str, *, model: str | None = None, dimension: int | None = None
    ) -> List[float]:
        """Generate a single embedding for the provided text."""
        model_name = model or self.model
        dims = dimension or self.dimension
        with self.tracer.observe(
            as_type="embedding",
            name="adapters.llm.openai_embedding_adapter.generate_embedding",
            input={"model": model_name, "dimension": dims},
        ):
            response = await self.client.embeddings.create(
                model=model_name, input=text, dimensions=dims
            )
            embedding = response.data[0].embedding
            return embedding

    async def generate_embeddings_batch(
        self, texts: List[str], *, model: str | None = None, dimension: int | None = None
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        model_name = model or self.model
        dims = dimension or self.dimension
        with self.tracer.observe(
            as_type="embedding",
            name="adapters.llm.openai_embedding_adapter.generate_embeddings_batch",
            input={
                "model": model_name,
                "dimension": dims,
                "batch_size": len(texts),
            },
        ):
            response = await self.client.embeddings.create(
                model=model_name, input=texts, dimensions=dims
            )
            embeddings = [item.embedding for item in response.data]
            return embeddings
