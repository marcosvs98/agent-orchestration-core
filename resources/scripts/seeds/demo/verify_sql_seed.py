"""Check that the committed demo seed loaded, and loaded once.

Run after applying `resources/sql/demo_seed.sql` twice. The row counts come from the file's own
header comments, so the check tracks the artifact instead of hard-coding numbers that go stale.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        REPO_ROOT = _repo
        break
else:
    raise SystemExit("repository root not found")

from sqlalchemy import text

from infra.database import get_db

SQL_PATH = REPO_ROOT / "resources" / "sql" / "demo_seed.sql"
SECTION = re.compile(r"^-- (\w+) \((\d+) rows\)$", re.MULTILINE)


async def verify() -> None:
    expected = {name: int(count) for name, count in SECTION.findall(SQL_PATH.read_text())}
    if not expected:
        raise SystemExit(f"no table sections found in {SQL_PATH}")

    mismatches: list[str] = []
    async with get_db() as session:
        for table, count in sorted(expected.items()):
            actual = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            if actual != count:
                mismatches.append(f"{table}: expected {count}, found {actual}")

    if mismatches:
        for line in mismatches:
            print(line, file=sys.stderr)
        raise SystemExit(
            "demo seed did not load as expected — a second apply must not duplicate rows"
        )
    print(f"verified {len(expected)} tables from {SQL_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    asyncio.run(verify())
