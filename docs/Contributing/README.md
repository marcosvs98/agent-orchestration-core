# Contributing (documentation)

This repository does not accept contributions — issues and discussions are disabled and pull
requests are closed without review. The conventions below are for whoever forks it.

For code conventions and architectural invariants, see the repository root **`CONTRIBUTING.md`**.
For local setup, see **`DEVELOPMENT.md`**.

## Documentation conventions

- **New Markdown files and folders** under `docs/` must use **English** file names, preferably **kebab-case** (e.g. `runtime-vs-authoring.md`, `documentation-map.md`). Do not add new Portuguese filenames.
- **Substance over pointers:** each page should stand on its own; avoid docs that only link elsewhere without context.
- **Persistence:** when you add a table in Alembic (`op.create_table`), update [Persistence tables](../Glossary/persistence-tables.md) in the same change.
- **Cross-links:** glossary entries should link to deep docs and back where helpful ([Glossary index](../Glossary/index.md)).

## Building the docs site

```bash
uv sync --extra docs
uv run mkdocs build
```

Fix any warnings about missing pages before merging.
