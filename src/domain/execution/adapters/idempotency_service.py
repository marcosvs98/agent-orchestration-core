import contextlib
from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from settings import IDEMPOTENCY_TTL_SECONDS


class IdempotencyService:
    def __init__(self, redis_adapter: RedisAdapter, tracer: RuntimeTracerPort) -> None:
        self.redis = redis_adapter
        self.tracer = tracer

    @staticmethod
    def build_key(*, tenant_id: UUID, endpoint: str, idempotency_key: str) -> str:
        return f"idempotency:{tenant_id}:{endpoint}:{idempotency_key}"

    async def try_acquire(self, key: str) -> bool:
        with (
            self.tracer.observe(
                as_type="tool",
                name="domain.execution.idempotency.try_acquire",
                input={"key": key},
            ):
            return bool(
                await self.redis.set_if_not_exists(
                    key,
                    {"status": "PROCESSING"},
                    ttl=IDEMPOTENCY_TTL_SECONDS,
                )
            )

    async def get(self, key: str) -> dict | None:

        with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.idempotency.get",
                input={"key": key},
            ):
            return await self.redis.get(key)

    async def set_result(self, key: str, data: dict) -> None:
       
        with self.tracer.observe(
                as_type="tool",
                name="domain.execution.idempotency.set_result",
                input={"key": key},
            ):
            await self.redis.set(key, data, ttl=IDEMPOTENCY_TTL_SECONDS)
