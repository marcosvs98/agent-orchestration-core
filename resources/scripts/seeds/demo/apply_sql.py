"""Apply the committed demo seed SQL using the project's own database connection.

The file is plain SQL — `psql -v ON_ERROR_STOP=1 -f resources/sql/demo_seed.sql` does the same
thing. This exists because `psql` is not installed everywhere, and requiring a client that a new
developer may not have would recreate the onboarding blocker the SQL seed was meant to remove.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        REPO_ROOT = _repo
        break
else:
    raise SystemExit("repository root not found")

from infra.database import engine

SQL_PATH = REPO_ROOT / "resources" / "sql" / "demo_seed.sql"


async def apply() -> None:
    if not SQL_PATH.is_file():
        raise SystemExit(f"{SQL_PATH} not found — run `make seed-demo-export` first")
    script = SQL_PATH.read_text(encoding="utf-8")

    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        # asyncpg prepares every statement it is given, and a prepared statement may hold only
        # one command. The driver connection's `execute` uses the simple query protocol, which
        # runs the whole script — including its own BEGIN/COMMIT — in one round trip.
        await raw.driver_connection.execute(script)

    await engine.dispose()
    print(f"applied {SQL_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    asyncio.run(apply())
