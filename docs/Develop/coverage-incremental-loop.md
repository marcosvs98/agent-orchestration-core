# Coverage incremental loop

CI enforces **`--cov-fail-under=90`** on the **measured** `src/` surface. That is not 90% of the
codebase: the `omit` list in `[tool.coverage.run]` still excludes files from the denominator.

| Scope | Statements | Coverage | How to measure |
|-------|-----------:|---------:|----------------|
| Measured surface (the gate) | ~13,456 | ~90.7% | `uv run python -m pytest` |
| Whole codebase | ~20,712 | ~74% | `uv run python -m pytest --cov-config=/dev/null --cov=src --cov-fail-under=0` |

Always quote both numbers. A gate over part of the tree that is reported as if it covered all of it
is worse than no gate, because it reads as assurance.

## Two rules

1. **Never add an `omit` entry.** An omitted file is invisible to the gate — a regression in it
   cannot fail CI. Write the test instead. The list is being retired, not extended.
2. **Never add an `--ignore` to `addopts`.** There are none today. A suppressed failing test is
   worse than a missing test: it looks like coverage while asserting nothing. This was the state
   the register found — 12 files plus a whole directory suppressed, hiding 35 real failures,
   four of which were live defects.

## Retiring the omit list

Work in tranches, highest risk first, and re-pin `--cov-fail-under` to the honest floor after each:

1. Pick a tranche (~15–20 files). Order by blast radius: auth and tenant isolation, then execution,
   then everything else. Prefer files already well covered by existing tests — those were pure
   denominator-gaming and cost nothing to readmit.
2. Delete those entries, run with `--cov-fail-under=0`, and read the new aggregate.
3. Write tests for anything the tranche exposes below the floor you want to hold.
4. Re-pin the gate just under the measured value and update the numbers in this file,
   `README.md` §8 and `CLAUDE.md`.

The percentage will fall as the denominator grows. That is the point: the number gets smaller and
starts meaning something. Two tranches have been retired so far — the security- and
execution-adjacent modules (`utils/auth.py`, `services/execution_boundary.py`,
`access_policy_service`, `governance_policies_service`, `rate_limit_service`, `auth_service`,
`tool_orchestrator`, `http_tool_executor`, `tenant_mcp_gateway`, …), then 19 modules that were
already covered. 74 entries remain.

## Operating loop

1. Run the suite the way CI does.
2. Inspect the HTML report (`htmlcov/`) for gaps in **non-omitted** files.
3. Add tests. If a file is omitted and you are touching it, take it off the list in the same PR.

## Related

- [Dead code pipeline](dead-code-pipeline.md) — correlates Vulture with coverage and `omit`
- `pyproject.toml` `[tool.coverage.run]`
