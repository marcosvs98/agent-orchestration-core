from __future__ import annotations

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

import settings
from domain.rag.ports.queue import EmbeddingJobQueuePort
from domain.rag.schemas.embedding_job import EmbeddingJobPayload


class ArqEmbeddingQueueAdapter(EmbeddingJobQueuePort):
    def __init__(self, queue_name: str | None = None) -> None:
        self.queue_name = queue_name or settings.EMBEDDING_QUEUE_NAME
        self._pool: ArqRedis | None = None

    async def enqueue_embedding_job(self, *, payload: EmbeddingJobPayload) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job(
            self.queue_name,
            payload.model_dump(mode="json"),
            _job_try=1,
        )

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(
                RedisSettings(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    database=settings.REDIS_DB,
                    ssl=settings.REDIS_SSL,
                )
            )
        return self._pool
