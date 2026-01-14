#!/bin/bash
set -e

export ENVIRONMENT=${ENVIRONMENT:-development}
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-1}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export TIMEOUT=${TIMEOUT:-120}

echo "Waiting for database connection"
postgres_ready() {
python3 << END
import os
import sys
import asyncio
import asyncpg
from urllib.parse import urlparse

async def connect():
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("DATABASE_URL not found")
            sys.exit(-1)

        parsed = urlparse(database_url.replace('postgresql+asyncpg://', 'postgresql://'))
        user = parsed.username or 'postgres'
        password = parsed.password or 'password'
        database = parsed.path.lstrip('/') or 'agent_router'
        host = parsed.hostname or 'localhost'
        port = parsed.port or 5432

        conn = await asyncpg.connect(
            user=user,
            password=password,
            database=database,
            host=host,
            port=port
        )
        await conn.close()
        print("Connected to database")
        sys.exit(0)
    except Exception as e:
        print(e)
        sys.exit(-1)

try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(connect())
finally:
    loop.close()
END
}

until postgres_ready; do
  >&2 echo "PostgreSQL is not available yet - waiting..."
  sleep 1
done

echo "PostgreSQL is ready"

echo "Running migrations (idempotent)..."
alembic upgrade head


if [[ $ENVIRONMENT = 'development' ]] ; then
  gunicorn "app:create_app()" \
    --worker-class uvicorn_workers.RestartableUvicornWorker \
    --bind 0.0.0.0:$PORT \
    --graceful-timeout 0 \
    --timeout 0 \
    --log-level DEBUG \
    --access-logfile - \
    --chdir $PYTHONPATH \
    --reload
else
  gunicorn "app:create_app()" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --graceful-timeout $TIMEOUT \
    --timeout $TIMEOUT \
    --log-level $LOG_LEVEL \
    --access-logfile - \
    --workers $WORKERS
fi