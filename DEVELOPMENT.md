# Development

Local setup and commands for **agent-orchestration-core**.

## Prerequisites

- Python **3.12** (see `pyproject.toml`).
- [uv](https://docs.astral.sh/uv/) recommended for environments and runs.

## Bootstrap

```bash
uv sync --all-extras --all-groups
```

(`[project.optional-dependencies] dev` brings pytest and pytest-cov; `[dependency-groups] dev` adds ruff, mypy, vulture, and related tools.)

## Running tests

Default test paths are `tests/unit` and `tests/integration` (see `pyproject.toml`). Validation integration tests are excluded by default (`-m "not validation_integration"`).

```bash
uv run python -m pytest
```

### Coverage

Coverage is collected for `src/` with reports in `htmlcov/` and `coverage.xml`.

```bash
uv run python -m pytest tests/unit tests/integration -m "not validation_integration"
```

**Policy:** CI enforces **`--cov-fail-under=95`** on the measured `src/` surface (see `pyproject.toml` `[tool.coverage.run] omit`). To iterate without failing the gate locally:

```bash
uv run python -m pytest tests/unit tests/integration --cov=src --cov-fail-under=0 -q
```

Use `coverage report --show-missing` or the HTML report to find gaps, add tests, then bump the floor when stable.

## Quality: dead code and static analysis

Ruff (lint), Vulture (unused code), optional mypy, and a **correlation** step that crosses Vulture with `coverage.xml` and the coverage **`omit`** list are documented in [docs/Develop/dead-code-pipeline.md](docs/Develop/dead-code-pipeline.md). CI runs Ruff and Vulture-vs-baseline; mypy is informational until type debt is reduced.

## Codecov (CI)

Uploads use [Codecov](https://codecov.io). Configure a repository secret **`CODECOV_TOKEN`** in GitHub Actions (Settings → Secrets and variables → Actions). The token is not committed to the repository.

## Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Docker

If the repository ships a `docker-compose` or `Makefile`, prefer those entry points for Postgres/Redis-backed integration or validation suites; see `docs/Deployment/docker.md`.
