from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlparse

import asyncpg


async def wait_for_db() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not found")
    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    user = parsed.username or "postgres"
    password = parsed.password or "password"
    database = parsed.path.lstrip("/") or "agent_router"
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    retries = int(os.getenv("DB_WAIT_RETRIES", "30"))
    delay = float(os.getenv("DB_WAIT_DELAY", "1"))
    for attempt in range(retries):
        try:
            conn = await asyncpg.connect(
                user=user,
                password=password,
                database=database,
                host=host,
                port=port,
            )
            await conn.close()
            return
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)


if __name__ == "__main__":
    try:
        asyncio.run(wait_for_db())
        sys.exit(0)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
