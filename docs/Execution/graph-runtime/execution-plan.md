# Execution plan

Defined in `src/domain/execution/services/graph_runtime/execution_plan.py`.

## `CompiledEdge`

Frozen Pydantic model:

- `from_node`, `to_node` — string ids from the snapshot
- `edge_kind` — `EdgeKind` from `domain.flows.schemas.graph` (`NORMAL`, `LOOP`, …)
- `compiled_condition` — **list** AST produced at authoring/compile time (from snapshot `compiled_condition`); evaluated at runtime (see [Edge evaluator](edge-evaluator.md))
- `order` — stable ordering when iterating edges from the same source node

## `ExecutionPlan`

Frozen Pydantic model:

- `start_node_id` — entry node
- `ordered_nodes` — node ids in snapshot iteration order (compiler preserves discovery order)
- `adjacency_map` — maps **source node id** → list of `CompiledEdge` (outgoing edges)
- `terminal_nodes` — ids whose `type` is a **terminal** node kind (e.g. `ResponseBuilder`, `HumanFallback` — see compiler)
- `structural_hash` — passed through from compile call (typically graph hash)
- `nodes` — raw node id → spec dict from snapshot (`type`, `config`, …)
- `available_tools` — list of `AvailableTool` (`domain.tools.schemas.tools`); may be empty when the compiler is invoked without tools

The executor treats the plan as **immutable** for the duration of a run.

## Related

- [Graph compiler](graph-compiler.md)
