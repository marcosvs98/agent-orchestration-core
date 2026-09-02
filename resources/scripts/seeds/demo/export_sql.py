"""Export the seeded demo tenant as one idempotent SQL file.

The Python seeds stay the generator — they compile the flow graph and call the embedding provider,
neither of which can be expressed as static SQL without freezing values that drift. This script runs
after them and captures the *result*, so consumers can load the demo with psql alone: no Python, no
network, no OpenAI key.

    export DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router
    make migrate && make seed-demo          # generate
    PYTHONPATH=src uv run python resources/scripts/seeds/demo/export_sql.py

Run it against a database that holds **only** the demo seed. Everything it finds for the demo tenant
(plus the global catalogues below) ends up in the file.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import pkgutil
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        sys.path.insert(0, str(_repo / "resources" / "scripts"))
        REPO_ROOT = _repo
        break
else:
    raise SystemExit("repository root not found")

import sqlalchemy as sa
from sqlalchemy.schema import sort_tables

import infra.database.models as models_package
from infra.database import get_db
from infra.database.models.base import ORMBaseModel
from seeds.demo.ids import TENANT_DEMO_ID

OUTPUT_PATH = REPO_ROOT / "resources" / "sql" / "demo_seed.sql"

# Execution history, caches and audit trails. A seed ships configuration, not runs.
EXCLUDED_TABLES = {
    "agent_run",
    "authoring_event",
    "conversation_summary",
    "end_user",
    "execution_event",
    "flow_run",
    "flow_run_lock",
    "graph_state",
    "interaction",
    "llm_usage_ledger",
    "node_run",
    "onboarding_run",
    "rag_query_cache",
    "rag_usage_counter",
    "response_artifact",
    "run_failure",
    "semantic_answer_cache",
    "session",
    "sla_case",
    "step_run",
    "tool_run",
    "user_memory_profile",
}

# Tables with no tenant_id that the demo seed populates as shared catalogues.
GLOBAL_TABLES = {
    "llm_pricing",
    "model",
    "node_prompt",
    "node_template",
}


def _quote(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (UUID, datetime, date)):
        return _quote(str(value))
    if isinstance(value, (dict, list)):
        return _quote(json.dumps(value, ensure_ascii=True, sort_keys=True))
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def _literal(column: sa.Column, value: Any) -> str:
    if value is None:
        return "NULL"
    type_name = str(column.type).lower()
    if type_name.startswith("vector"):
        return _quote("[" + ",".join(repr(float(v)) for v in value) + "]") + "::vector"
    if "jsonb" in type_name or "json" in type_name:
        return _quote(json.dumps(value, ensure_ascii=True, sort_keys=True)) + "::jsonb"
    if type_name.startswith("uuid"):
        return _quote(str(value)) + "::uuid"
    if "timestamp" in type_name:
        return _quote(str(value)) + "::timestamptz"
    return _quote(value)


def _exportable_tables() -> list[sa.Table]:
    for module in pkgutil.walk_packages(models_package.__path__, models_package.__name__ + "."):
        importlib.import_module(module.name)
    ordered = sort_tables(ORMBaseModel.metadata.tables.values())
    return [table for table in ordered if table.name not in EXCLUDED_TABLES]


def _select_for(
    table: sa.Table, collected: dict[tuple[str, str], set[Any]]
) -> sa.Select | None:
    """Rows of `table` that belong to the demo tenant.

    Three ways to belong, combined with OR rather than checked in priority order:

    * the row carries `tenant_id` — but the column is nullable on several version tables, and the
      demo's `billing_policy_version` leaves it NULL while its parent policy is tenant-scoped;
    * the table is a shared catalogue;
    * the row links, in either direction, to something already collected. Downward links pull in
      `flow_version`, `node`, `agent_version`, `rag_chunk`; upward links pull in parents such as
      `condition_expression`, which nothing points at from the tenant side but `routing_rule`
      requires.
    """

    stmt = sa.select(table)
    if table.name in GLOBAL_TABLES:
        return stmt

    link_clauses = []
    for column in table.columns:
        for foreign_key in column.foreign_keys:
            parent = foreign_key.column
            if parent.table.name in GLOBAL_TABLES:
                continue
            values = collected.get((parent.table.name, parent.name))
            if values:
                link_clauses.append(column.in_(values))

    for column in table.primary_key.columns:
        referencing = collected.get(("__referenced__", f"{table.name}.{column.name}"))
        if referencing:
            link_clauses.append(column.in_(referencing))

    if "tenant_id" in table.columns:
        # The tenant column is authoritative and never widened by a link: a shared catalogue such
        # as `tool` would otherwise drag in every tenant's `tool_config`, and from there the whole
        # database. Links only rescue rows whose tenant column is NULL, as the demo's
        # `billing_policy_version` is.
        owned = table.c.tenant_id == TENANT_DEMO_ID
        if not link_clauses:
            return stmt.where(owned)
        return stmt.where(
            sa.or_(owned, sa.and_(table.c.tenant_id.is_(None), sa.or_(*link_clauses)))
        )

    if not link_clauses:
        return None
    return stmt.where(sa.or_(*link_clauses))


def _record_collected(
    table: sa.Table, rows: list[dict[str, Any]], collected: dict[tuple[str, str], set[Any]]
) -> None:
    """Index a table's rows so later tables can find their relatives."""

    for column in table.columns:
        if not isinstance(column.type, (sa.Uuid, sa.String, sa.Integer)):
            continue
        values = {row[column.name] for row in rows if row.get(column.name) is not None}
        if not values:
            continue
        collected.setdefault((table.name, column.name), set()).update(values)
        for foreign_key in column.foreign_keys:
            parent = foreign_key.column
            key = ("__referenced__", f"{parent.table.name}.{parent.name}")
            collected.setdefault(key, set()).update(values)


def _ident(name: str) -> str:
    """Quote every column identifier: `limit` and `metadata` are reserved words in Postgres."""

    return '"' + name.replace('"', '""') + '"'


def _deferred_columns(table: sa.Table, position: dict[str, int]) -> list[str]:
    """Foreign-key columns pointing at a table emitted later in the file.

    `tenant.default_flow_version_id` → `flow_version` → `flow` → `tenant` is a genuine cycle, so no
    ordering satisfies it. Those columns are inserted NULL and set by an UPDATE at the end.
    """

    deferred = []
    own = position[table.name]
    for column in table.columns:
        for foreign_key in column.foreign_keys:
            target = foreign_key.column.table.name
            if position.get(target, -1) > own and column.nullable:
                deferred.append(column.name)
    return deferred


def _update_statement(table: sa.Table, row: dict[str, Any], columns: list[str]) -> str:
    assignments = ", ".join(
        f"{_ident(name)} = {_literal(table.columns[name], row[name])}" for name in columns
    )
    predicate = " AND ".join(
        f"{_ident(column.name)} = {_literal(column, row[column.name])}"
        for column in table.primary_key.columns
    )
    return f"UPDATE {table.name} SET {assignments} WHERE {predicate};"


def _insert_statement(
    table: sa.Table, row: dict[str, Any], deferred: list[str] | None = None
) -> str:
    skip = set(deferred or [])
    columns = [name for name in table.columns.keys() if name in row and name not in skip]
    values = ", ".join(_literal(table.columns[name], row[name]) for name in columns)
    primary_key = [column.name for column in table.primary_key.columns]
    updatable = [name for name in columns if name not in primary_key]
    conflict_target = ", ".join(_ident(name) for name in primary_key)
    if updatable:
        assignments = ", ".join(
            f"{_ident(name)} = EXCLUDED.{_ident(name)}" for name in updatable
        )
        conflict = f"ON CONFLICT ({conflict_target}) DO UPDATE SET {assignments}"
    else:
        conflict = f"ON CONFLICT ({conflict_target}) DO NOTHING"
    return (
        f"INSERT INTO {table.name} ({', '.join(_ident(name) for name in columns)})\n"
        f"VALUES ({values})\n"
        f"{conflict};"
    )


async def export() -> None:
    tables = _exportable_tables()
    sections: list[str] = []
    exported_rows = 0
    exported_tables = 0

    collected: dict[tuple[str, str], set[Any]] = {}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}

    async with get_db() as session:
        # Sweep repeatedly: a table can become reachable only after a relative is collected, in
        # either direction. Converges in a handful of passes; the bound is a safety net.
        for _ in range(6):
            added = False
            for table in tables:
                stmt = _select_for(table, collected)
                if stmt is None:
                    continue
                result = await session.execute(stmt.order_by(*table.primary_key.columns))
                rows = [dict(row) for row in result.mappings().all()]
                if not rows:
                    continue
                known = rows_by_table.get(table.name)
                if known is not None and len(known) == len(rows):
                    continue
                rows_by_table[table.name] = rows
                _record_collected(table, rows, collected)
                added = True
            if not added:
                break

    position = {table.name: index for index, table in enumerate(tables)}
    deferred_updates: list[str] = []

    for table in tables:
        rows = rows_by_table.get(table.name)
        if not rows:
            continue
        deferred = [
            name
            for name in _deferred_columns(table, position)
            if any(row.get(name) is not None for row in rows)
        ]
        exported_tables += 1
        exported_rows += len(rows)
        body = "\n\n".join(_insert_statement(table, row, deferred) for row in rows)
        sections.append(f"-- {table.name} ({len(rows)} rows)\n{body}")
        for row in rows:
            present = [name for name in deferred if row.get(name) is not None]
            if present:
                deferred_updates.append(_update_statement(table, row, present))

    if deferred_updates:
        sections.append(
            "-- Circular references, set once both sides exist\n"
            + "\n".join(deferred_updates)
        )

    header = (
        "-- Demo tenant seed, generated by resources/scripts/seeds/demo/export_sql.py.\n"
        "-- Do not edit by hand: regenerate with `make seed-demo-export` after changing the\n"
        "-- Python seeds, the flow graph, or the embedding model. Compiled graph hashes and\n"
        "-- embedding vectors are captured values and drift if their producers change.\n"
        f"-- Tenant: {TENANT_DEMO_ID}\n"
        f"-- Tables: {exported_tables}  Rows: {exported_rows}\n"
        "\nBEGIN;\n"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + "\n\n".join(sections) + "\n\nCOMMIT;\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({exported_tables} tables, {exported_rows} rows)")


if __name__ == "__main__":
    asyncio.run(export())
