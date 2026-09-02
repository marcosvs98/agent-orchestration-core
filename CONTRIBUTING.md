# Contributing

**This repository does not accept contributions.** Issues, projects and discussions are disabled,
and pull requests are closed without review. That is a decision about maintenance capacity, not a
judgement about any particular change.

It is published as a reference implementation and as source for anyone who wants to run or fork
it — not as a collaborative project.

## What you may do

The project is licensed under [Apache-2.0](LICENSE). You may run, modify, redistribute and use it
commercially under the terms of that licence. **Forking is the supported way to build on it.**

## Reporting a vulnerability

This is the one channel that stays open. See [SECURITY.md](SECURITY.md) and use GitHub's private
vulnerability reporting — not a public channel.

---

The rest of this page documents the constraints the codebase is built on. It is written for
whoever forks it and has to keep it coherent.

## Architectural invariants

These are not style preferences. A change that breaks one will produce a subtly wrong system
rather than a failing test.

1. `tenant_id` is resolved from the JWT security context, never read from a request body.
2. Domain code does not import from `infra/` or `adapters/`. Dependencies point inward: define a
   protocol in the domain and inject the implementation.
3. Published versions are immutable. A `PUBLISHED` flow, agent, or policy version is never edited
   in place — publish a new version.
4. Execution never mutates definitions. `FlowRun`, `NodeRun`, `AgentRun` and `ToolRun` are
   append-only.
5. LLM calls stay inside node implementations. The model classifies, extracts, and formats; tool
   invocation and persistence happen deterministically in executor logic around it.

## Working on a fork

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
uv run pre-commit install
```

Before committing:

```bash
uv run pre-commit run --all-files
uv run python -m pytest
```

Do not skip the hooks with `--no-verify`; fix what they flag.

## Tests

There is no CI in this repository — the workflows were removed. Coverage is therefore only
enforced by whoever runs the suite. `pyproject.toml` still carries the threshold and the `omit`
list, so `pytest` reproduces the gate locally.

- `tests/unit/` — mocked repositories and adapters. No database, no network.
- `tests/integration/` — real Postgres and Redis, marked `@pytest.mark.integration`.
- `tests/bdd/` — Gherkin features, marked `@pytest.mark.bdd`.

Never add a file to the coverage `omit` list or an `--ignore` entry to `addopts` to get a run
green. A suppressed test is worse than a missing one, because it looks like coverage.

## Code conventions

- No comments. Names, types, and structure carry the meaning; comments go stale and the diffs
  get noisier for it.
- No docstrings unless the module is an exported boundary with a contract a maintainer would
  otherwise miss.
- Type annotations on every public function, method, and module boundary.
- No `getattr`/`setattr` for attributes that are statically known.
- No imports inside functions. Module level only, with `if TYPE_CHECKING:` for annotation-only
  imports.
- Validate at system boundaries — JWT claims, request bodies, external API responses. Do not add
  error handling for states your own invariants already exclude.

## Commit messages

The published history uses a Conventional Commits **type** as the prefix, with no scope:

```text
feat: Add cursor pagination to flow-run listing
```

Types in use: `feat`, `fix`, `refactor`, `chore`, `test`, `docs`, `ci`, `build`. Sub-lines go in
the body, below a blank line, and only when they add something the subject cannot carry.

## Database migrations

Every schema change needs an Alembic revision:

```bash
PYTHONPATH=src uv run alembic revision --autogenerate -m "short description"
```

Read the generated file before committing — autogenerate misses server defaults, sequences, and
some index changes. Never edit a revision that has already been applied anywhere real.

## Known limitations

Before assuming a behaviour is a defect, read [`docs/Develop/limitations.md`](docs/Develop/limitations.md).
Several rough edges are deliberate trade-offs and are documented there rather than hidden.
