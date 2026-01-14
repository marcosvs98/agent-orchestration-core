import asyncio
import json
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from redis import asyncio as aioredis

from settings import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT, REDIS_SSL
from adapters.observability.logging import get_logger

logger = get_logger()

P = ParamSpec("P")
R = TypeVar("R")


def silent_mode_wrapper(
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R | bool]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | bool:
        self = args[0]
        if self.silent_mode:
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.exception("Cache silent exception")
                return False
        return await func(*args, **kwargs)

    return wrapper


class RedisAdapter:
    """Redis cache adapter using asyncio client."""

    def __init__(self, silent_mode: bool = False) -> None:
        self.silent_mode = silent_mode
        self.client = self.__open_connection()

    def __del__(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.client.aclose())
            else:
                loop.run_until_complete(self.client.aclose())
        except Exception:
            pass

    @staticmethod
    def __open_connection() -> aioredis.client.Redis:
        scheme = "rediss" if REDIS_SSL else "redis"
        auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
        redis_url = f"{scheme}://{auth}{REDIS_HOST}:{REDIS_PORT}/0"
        return aioredis.from_url(redis_url, decode_responses=True, encoding="utf-8")

    @silent_mode_wrapper
    async def get(self, key: str) -> dict[str, Any] | None:
        data = await self.client.get(key)
        return json.loads(data) if data else None

    @silent_mode_wrapper
    async def set(self, key: str, data: dict[str, Any], ttl: int = 300) -> None:
        await self.client.set(key, json.dumps(data, default=str), ex=ttl)

    @silent_mode_wrapper
    async def set_if_not_exists(self, key: str, data: dict[str, Any], ttl: int = 300) -> bool:
        result = await self.client.set(key, json.dumps(data, default=str), ex=ttl, nx=True)
        return bool(result)

    @silent_mode_wrapper
    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    @silent_mode_wrapper
    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        value = await self.client.incr(key)
        if int(value) == 1:
            await self.client.expire(key, ttl)
        return int(value)
