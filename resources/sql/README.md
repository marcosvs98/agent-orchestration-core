# Demo seed SQL

`demo_seed.sql` is the demo tenant as data: 51 tables, ~800 rows, including the RAG corpus with its
embedding vectors. Applying it needs a migrated database and nothing else — no Python seeds, no
OpenAI key, no second service.

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:password@127.0.0.1:5432/agent_router'
make migrate
make seed-demo
```

`make seed-demo` applies the file through the project's own connection because `psql` is not
installed everywhere. The file is ordinary SQL, so any client works:

```bash
psql "postgresql://postgres:password@127.0.0.1:5432/agent_router" -v ON_ERROR_STOP=1 -f resources/sql/demo_seed.sql
```

Every statement is `INSERT … ON CONFLICT DO UPDATE`, and the whole file is one transaction:
re-applying converges rather than duplicating, and a failure part-way leaves nothing behind.

## Why it is generated, not written

Four of the 27 Python seeds compute values that cannot be written by hand without going stale:

| Seed | Computation |
|------|-------------|
| `seed_05_tool` | parses an OpenAPI document into tool contracts |
| `seed_11_graph` | runs the graph compiler; `graph_hash` changes when the compiler changes |
| `seed_26_flow_snapshot_deployment` | SHA-256 over the snapshot payload |
| `seed_21_rag`, `seed_22_tool_catalog_rag` | real OpenAI embedding calls, 3072 dimensions |

So the Python seeds remain the **generator** and this file is the **artifact**:

```bash
make seed-demo-python     # generate: needs a database and, for the RAG corpus, an OpenAI key
make seed-demo-export     # capture:  writes resources/sql/demo_seed.sql
```

Run the export against a database holding **only** the demo seed. The exporter walks the ORM
metadata in foreign-key order and takes rows that belong to the demo tenant — by tenant column, by
shared catalogue, or by following a foreign key in either direction. Execution history, caches and
audit trails are excluded: a seed ships configuration, not runs.

Two structural details worth knowing if you edit the exporter:

- **`tenant.default_flow_version_id` is a genuine cycle** (tenant → flow_version → flow → tenant).
  Forward references are inserted `NULL` and set by `UPDATE` statements at the end of the file.
- **The tenant column is authoritative and never widened by a link.** Otherwise a shared catalogue
  such as `tool` drags in every tenant's `tool_config`, and from there the whole database — which
  the first version of the exporter did, producing 16 tenants instead of one.

## What CI checks, and what it does not

The `demo-seed` job migrates a fresh Postgres, applies this file **twice**, and asserts the row
counts in the file's header. That catches broken SQL, foreign-key ordering, reserved-word
identifiers, non-idempotent statements, and any migration that renames or tightens a column the
seed writes.

It does **not** prove the file still matches the Python seeds — regenerating needs an OpenAI key,
and embeddings are not byte-stable. After changing a seed, the flow graph, or the embedding model,
re-run `make seed-demo-export` and commit the result. The file header repeats this.
