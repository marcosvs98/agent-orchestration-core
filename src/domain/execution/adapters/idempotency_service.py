from uuid import UUID

from adapters.cache.redis_adapter import RedisAdapter
from settings import IDEMPOTENCY_TTL_SECONDS


class IdempotencyService:
    def __init__(self, redis_adapter: RedisAdapter) -> None:
        self.redis = redis_adapter

    @staticmethod
    def build_key(*, tenant_id: UUID, endpoint: str, idempotency_key: str) -> str:
        return f"idempotency:{tenant_id}:{endpoint}:{idempotency_key}"

    async def try_acquire(self, key: str) -> bool:
        return bool(
            await self.redis.set_if_not_exists(
                key,
                {"status": "PROCESSING"},
                ttl=IDEMPOTENCY_TTL_SECONDS,
            )
        )

    async def get(self, key: str) -> dict | None:
        return await self.redis.get(key)

    async def set_result(self, key: str, data: dict) -> None:
        await self.redis.set(key, data, ttl=IDEMPOTENCY_TTL_SECONDS)
