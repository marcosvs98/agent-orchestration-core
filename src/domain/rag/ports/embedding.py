from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    async def generate_embedding(
        self,
        text: str,
        *,
        model: str | None = None,
        dimension: int | None = None,
    ) -> list[float]:
        ...

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimension: int | None = None,
    ) -> list[list[float]]:
        ...
