# Dead code, static analysis, and deprecation

This repository combines **Ruff**, **mypy**, **Vulture**, **pytest + coverage**, and a small **correlation script** so we do not treat coverage `omit` files as “uncovered by accident” when triaging dead code.

## Commands (canonical)

| Step | Command |
|------|---------|
| Lint (Pyflakes + syntax errors) | `uv run ruff check src` |
| Format check (optional) | `uv run ruff format --check src` |
| Type check | `uv run mypy src` (see note below) |
| Tests + coverage | `uv run python -m pytest tests/unit tests/integration -m "not validation_integration"` |
| Vulture report | `bash support/scripts/quality/vulture_report.sh` → `artifacts/vulture-latest.txt` |
| Baseline diff (CI gate) | `bash support/scripts/quality/vulture_diff.sh` (compares to `artifacts/vulture-baseline.txt`) |
| Correlate Vulture + coverage + omit | `uv run python support/scripts/quality/correlate_dead_code.py` |

**mypy:** Configuration is in `pyproject.toml` (`[tool.mypy]`). There is significant historical type debt; CI runs mypy with **`continue-on-error: true`** until the backlog is addressed. Do not interpret green CI as “mypy clean.”

**Ruff:** `[tool.ruff.lint] select = ["E9", "F"]` starts with **pycodestyle errors** and **Pyflakes** only. Expand rules deliberately (e.g. `I`, `UP`) once the codebase is ready.

## Coverage `omit` and correlation

`[tool.coverage.run] omit` in `pyproject.toml` removes paths from the **measured** surface used for `--cov-fail-under=95`. A file can be “omitted on purpose” while still being live code.

The script `support/scripts/quality/correlate_dead_code.py` reads:

1. A Vulture report (default `artifacts/vulture-latest.txt`).
2. `coverage.xml` from pytest-cov (paths are relative to `src/` in the XML).
3. The `omit` list from `pyproject.toml`.

It assigns each finding to:

| Category | Meaning |
|----------|---------|
| `ignore_omit` | Path matches an `omit` glob — do not use global coverage % alone to decide removal. |
| `strong_remove_candidate` | File is measured, line appears in `coverage.xml` with **0 hits** — strong signal to remove or test. |
| `investigate` | Measured line has hits &gt; 0 but Vulture still flags it, or the line is not listed (e.g. non-executable). |
| `no_coverage_data` | File not present in `coverage.xml` for this run (e.g. not imported in tests). |

See also [Coverage incremental loop](coverage-incremental-loop.md) for how the measured surface is managed.

## Vulture baseline and whitelist

- **Baseline (versioned):** `artifacts/vulture-baseline.txt` — sorted line-level snapshot; CI fails if `vulture-latest` has **new** lines not in the baseline (`support/scripts/quality/vulture_diff.sh`).
- **Whitelist:** `vulture_whitelist.py` — false positives (entrypoints, dynamic imports, etc.); pass it to Vulture as today in `vulture_report.sh`.

When Vulture reports new issues, either fix the code, extend the whitelist with a short comment, or **update the baseline in a dedicated PR** with team agreement.

## Deprecation policy (roadmap)

We do **not** turn on `pytest -W error::DeprecationWarning` for the full suite until the warning inventory is under control (dependencies may emit warnings).

**Convention (code):** For public APIs, prefer `warnings.warn("...", DeprecationWarning, stacklevel=2)` (adjust `stacklevel` to the caller). Document replacements in the message.

**Tests:** Use `pytest.mark.filterwarnings` where a test **expects** a deprecation, or isolate compatibility tests.

**Phases:**

| Phase | Behaviour |
|-------|-----------|
| **A (current)** | Default warning filter; no global error. Optionally run `pytest -W default::DeprecationWarning` locally and file issues for noisy call sites. |
| **B** | Optional CI job: `pytest -W error::DeprecationWarning` scoped to `tests/deprecation/` or migrated packages only. |
| **C** | Expand `-W error::DeprecationWarning` toward full `src` when the inventory is empty or filtered. |

CI does **not** enforce phase B/C by default; enable extra jobs when ready.

## CI overview

The workflow runs **Ruff** (hard fail), **mypy** (informational), **pytest + coverage** (existing gate, 95%), then **Vulture**, **correlation**, and **Vulture vs baseline** (hard fail on unexplained new Vulture lines). Dead-code artifacts are uploaded when tests succeed.
