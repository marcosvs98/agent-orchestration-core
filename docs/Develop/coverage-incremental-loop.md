# Coverage incremental loop

CI enforces **`--cov-fail-under=95`** on the **measured** `src/` surface. A long **`omit`** list in `[tool.coverage.run]` in `pyproject.toml` excludes selected files from the aggregate denominator (see comments there).

## Operating loop

1. Run tests with coverage (same paths as CI: `tests/unit`, `tests/integration`, excluding `validation_integration` markers as configured).
2. Inspect `coverage.xml` or HTML report for gaps in **non-omitted** files.
3. Add tests or, if justified, adjust `omit` with team agreement and update this mental model—not the global percentage in isolation.

## Related

- [Dead code pipeline](dead-code-pipeline.md) — correlates Vulture with coverage and `omit`
- `pyproject.toml` `[tool.coverage.run]`
