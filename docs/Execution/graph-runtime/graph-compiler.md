# Graph compiler

`GraphCompiler` (`src/domain/execution/services/graph_runtime/graph_compiler.py`) is a **pure** function object: `compile(snapshot, structural_hash, available_tools=None) -> ExecutionPlan`.

## Inputs

- **`snapshot`** — dict with at least `start_node`, `nodes` (id → spec with `type`), `edges` (list with `from_node`, `to_node`, `compiled_condition`, optional `edge_kind`)
- **`structural_hash`** — stored on `ExecutionPlan.structural_hash`
- **`available_tools`** — optional list merged into `ExecutionPlan.available_tools`

## Validation steps

1. **Start node** — `start_node` must exist in `nodes`.
2. **Edges** — non-empty; each edge must have **`compiled_condition`** (raises `compiled_condition_missing` if absent).
3. **Terminal nodes** — at least one node whose `type` is `ResponseBuilder` or `HumanFallback` (`no_terminal_nodes` if none).
4. **Adjacency** — edges sorted deterministically, packaged into `CompiledEdge` with monotonic `order`.
5. **Reachability** — DFS from `start_node` must visit **every** node id (`unreachable_nodes`).
6. **Cycles** — back-edges must use `EdgeKind.LOOP`; otherwise `cycle_not_marked_loop`.

## Outputs

Returns `ExecutionPlan` (see [Execution plan](execution-plan.md)).

## Tracing

Wrapped in `domain.execution.graph_compiler.compile` and nested `validate_structure`, `validate_reachability`, `validate_loops` spans.

## Related

- [Runtime executor](runtime-executor.md) — consumes the plan
- Authoring-time compilation of conditions lives in the flows domain; the snapshot must already contain `compiled_condition` for each edge
