# Edge evaluator

`EdgeEvaluator` (`src/domain/execution/services/graph_runtime/edge_evaluator.py`) compiles and evaluates **boolean expressions** for **edge conditions**. The authoring pipeline stores **pre-compiled** AST fragments on each edge (`compiled_condition` on `CompiledEdge`); runtime evaluation uses those structures with `EdgeEvaluator.is_true` and a **context** dict (typically derived from node output and execution state).

## Main API

- **`compile_condition(condition: str)`** — parses a **source** condition string with pyparsing (`BOOLEAN_EXPRESSION`), returns a JSON-serializable AST (via `_to_serializable`). On parse failure: `DomainValidationException` with `edge_condition_invalid`.

- **`collect_identifiers(compiled_condition)`** — walks the AST and returns top-level **identifier roots** used in path expressions (for static analysis / validation elsewhere).

- **`is_true(condition, context, compiled_condition=None)`** — evaluates either the provided compiled AST or recompiles from `condition`. The result must be a **bool** or `DomainValidationException` (`edge_evaluation_error` / `result_not_boolean`).

## Language (high level)

The module builds a grammar for:

- **Property paths** — identifiers with optional `[index]` segments (`SubstituteVal`), joined by `.`
- **Boolean operators** — `and`, `or`, `not`, parentheses
- **Comparisons** — binary operators including `=`, `==`, `!=`, ordering, `in`, Unicode variants as listed in `BINARY_OPERATORS`
- **Literals** — numbers, quoted strings, booleans, `none`

Helper evaluators (`LenVal`, built-in `FUNCTIONS` map) support common predicates (e.g. length, emptiness).

For the exact grammar, read `pyparsing` composition at the top of the file and `EdgeEvaluator._eval`.

## Runtime integration

`RuntimeExecutor._evaluate_edges` uses compiled conditions from the plan together with a context built from the **current node result** and counters — see `executor.py` for `EdgeEvaluator.is_true` call sites and failure mapping to `FlowFailureReason.EDGE_EVALUATION_ERROR`.

## Related

- [Runtime executor](runtime-executor.md)
- [Graph compiler](graph-compiler.md) — requires `compiled_condition` on each edge in the snapshot
