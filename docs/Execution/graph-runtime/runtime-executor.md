# Runtime executor

`RuntimeExecutor` (`src/domain/execution/services/graph_runtime/executor.py`) implements the **graph walk**: for each step it loads the node spec, **`registry.resolve(node_type)`**, runs **`execute`**, persists results, optionally **waits for input**, or completes the flow at a **terminal** node, otherwise **evaluates exactly one** matching outgoing edge.

## `run` parameters (selected)

- Identity: `tenant_id`, `session_id`, `interaction_id`, `flow_id`, `flow_version_id`, `flow_run_id`, `correlation_id`, `trace_id`
- **`input_payload`** — `FlowRunInput` (serialized into `ExecutionContext.input_payload`)
- **`plan`** — `ExecutionPlan`
- **`runtime_policy`** — `ResolvedRuntimePolicy | None`; definition dumped into `metadata["runtime_policy"]` for nodes
- **`start_node_id`**, **`initial_state`**, **`initial_memory`** — resume / fork
- **`on_content_delta`** — streaming callback for LLM nodes
- **`trace_context`** — must include `user_id` (raises `user_id_required` if missing)

## Loop limit

From `runtime_policy.definition.limits.max_loop_iterations` when set and valid; otherwise default **10**. Used with adjacency size to cap the main `for` loop (`max_steps`).

## Main loop (conceptual)

1. Build **`ExecutionContext`** with `current_node_id = start_node_id or plan.start_node_id`, state/memory, metadata including **runtime_policy**.
2. Optional **user context enrichment** gate seed in `state` when policy enables it.
3. For each step (bounded):
   - Resolve **`node_cls`**, instantiate **`node: NodeExecutor`**, **`create_node_run`** (RUNNING).
   - **`hook.on_node_start`** (or direct `NodeStarted` event).
   - **`await node.execute(context, config)`** with node `config` from snapshot.
   - Map result status, **`update_node_run_result`**, merge **`next_state`**, maintain **`_node_outputs_by_node_id`** in state (see `NODE_OUTPUTS_BY_NODE_ID_KEY`).
   - **`upsert_graph_state`** with `resume_to_node_id` when `NEEDS_INPUT`.
   - If **`NEEDS_INPUT`**: set flow to `WAITING_INPUT` / canonical `WAITING`, persist output, **return**.
   - If node type ∈ **`TERMINAL_NODE_TYPES`**: **`complete_flow_run`**, **`on_flow_complete`**, **return**.
   - Else **`_evaluate_edges`**: must get **exactly one** next node id; on 0 → `NO_MATCHING_EDGE`, on >1 → `MULTIPLE_MATCHING_EDGES`, on evaluator exception → `EDGE_EVALUATION_ERROR`.
   - Move `current_node_id` to next id; continue.

On failure paths, **`_fail_flow`** records reason and exceptions per `FlowFailureReason`.

## Types

- **`ExecutionContext`** — `src/domain/execution/services/graph_runtime/types.py`: ids, `state`, `memory`, `metadata`, `get_node_output(NodeType)`, `iteration_counters`, streaming callback.
- **`NodeResult`** — `node`, `status`, `data`, `error`, `metrics`, `next_state`, `memory`.
- **`NodeExecutor`** protocol — `async execute(context, config) -> NodeResult`.

## Related

- [Node registry](node-registry.md)
- [Edge evaluator](edge-evaluator.md)
- [Observability and hooks](../observability-and-hooks.md)
