# Contributing

Thank you for helping improve **agent-orchestration-core**. This document describes how we work day to day.

## Workflow

1. Open an issue or link a ticket before large changes, unless the fix is trivial (typos, single obvious bug).
2. Use short-lived branches from `main`.
3. Keep pull requests focused: one concern per PR when possible.
4. Ensure tests pass locally (see [DEVELOPMENT.md](DEVELOPMENT.md)).

## Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/) where practical, for example:

- `feat(execution): add guard for empty graph`
- `fix(rag): correct embedding dimension check`
- `docs: update architecture diagram`

## Tests and coverage

- Unit tests live under `tests/unit/**` and mirror `src/**`.
- Integration tests live under `tests/integration/**`.
- Run `pytest` as documented in [DEVELOPMENT.md](DEVELOPMENT.md).
- The repository policy is **≥80% line coverage** on `src/` (see DEVELOPMENT for the current enforced floor during the ramp-up).

## Code style

- Prefer matching existing patterns in the touched modules.
- Run `pre-commit` when installed (`pre-commit run --all-files`).

## Security

Please report sensitive issues as described in [SECURITY.md](SECURITY.md) instead of public issues.
