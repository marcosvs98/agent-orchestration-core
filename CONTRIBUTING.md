# Contributing

Thanks for looking at agent-orchestration-core. This page covers how to propose a change. For
setting up a working environment, see [DEVELOPMENT.md](DEVELOPMENT.md). For reporting a
vulnerability, see [SECURITY.md](SECURITY.md) — please do not open a public issue for that.

## Before you start

**This project has no licence yet.** Until one is added, the default of copyright law applies:
you may read the code, but redistribution and derivative works are not granted. We are not able
to merge contributions until licensing is resolved. Issues and discussion are welcome now;
pull requests may have to wait.

## Opening an issue

A useful bug report contains the version or commit, what you ran, what happened, and what you
expected instead. If the behaviour involves a flow run, the `flow_run_id` and the surrounding
log lines are worth more than a description of them.

Feature proposals are more likely to land if they name the bounded context they touch
(`src/domain/<context>/`) and say which of the architectural invariants below they interact with.

## Architectural invariants

These are not style preferences. A change that breaks one will be sent back regardless of how
well it is written.

1. `tenant_id` is resolved from the JWT security context, never read from a request body.
2. Domain code does not import from `infra/` or `adapters/`. Dependencies point inward: define a
   protocol in the domain and inject the implementation.
3. Published versions are immutable. A `PUBLISHED` flow, agent, or policy version is never edited
   in place — publish a new version.
4. Execution never mutates definitions. `FlowRun`, `NodeRun`, `AgentRun` and `ToolRun` are
   append-only.
5. LLM calls stay inside node implementations. The model classifies, extracts, and formats; tool
   invocation and persistence happen deterministically in executor logic around it.

## Making a change

```bash
uv sync --all-extras --all-groups
source .venv/bin/activate
uv run pre-commit install
```

Work in a branch. Keep the change set as small as the problem allows — a bug fix and a refactor
in one diff is two reviews wearing one hat.

Before pushing:

```bash
uv run pre-commit run --all-files
uv run python -m pytest
```

Both must pass. Do not skip the hooks with `--no-verify`; fix what they flag.

## Tests

Coverage is gated in CI. Add tests in proportion to risk — a regression test for every bug fix,
and a contract test at every boundary you change.

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

[Conventional Commits](https://www.conventionalcommits.org/) with a ticket-style scope:

```text
feat(AOC-123): add cursor pagination to flow-run listing
```

Use `no-ticket` as the scope when there is no ticket. Mark breaking changes with `!` after the
scope, or a `BREAKING CHANGE:` footer.

## Database migrations

Every schema change needs an Alembic revision:

```bash
PYTHONPATH=src uv run alembic revision --autogenerate -m "short description"
```

Read the generated file before committing — autogenerate misses server defaults, sequences, and
some index changes. Never edit a revision that has already been applied anywhere real.

## Review

Expect questions about correctness first and style second. A change that adds ambiguity without
clear value, introduces a silent fallback that hides a contract failure, or mixes a broad refactor
into a behavioural fix will be asked to split or narrow.
