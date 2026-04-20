from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from domain.rag.schemas.embedding_job import EmbeddingJobPayload

if TYPE_CHECKING:
    from arq.connections import ArqRedis


class EmbeddingJobQueuePort(Protocol):
    async def enqueue_embedding_job(self, *, payload: EmbeddingJobPayload) -> None: ...

    async def _get_pool(self) -> ArqRedis: ...
