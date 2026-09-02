# Non-LLM nodes

Nodes that do **not** subclass `LLMNodeExecutor` (or that use **moderation** instead of chat completion). Sources under `src/domain/execution/services/graph_runtime/nodes/`.

## `ContentModeration`

- **`NodeExecutor`**, `side_effect = False`, `deterministic = True`.
- Reads **`read_user_input(context)`**, calls **`ModerationProviderPort.moderate`** with config merged from node `config` and `runtime_policy.moderation`.
- Returns `flagged` and `categories` in `NodeResult.data`.
- Registry requires **`llm_moderation_provider`**.

## `ToolExecutor`

- **`NodeExecutor`**, `side_effect = True`, `deterministic = False`.
- Parses tool inputs from **`ToolResolver`** / state, applies **fan-out limits** from `runtime_policy.limits`, invokes **`ToolOrchestrator`** (HTTP/tool runs), persists via **`ExecutionRepository`**.
- Returns structured **`ToolExecutorOutput`**-style payloads in state (see `schemas/tool_executor.py`).

### Execution modes

Each operation resolves to a `ToolExecutionMode`:

| Mode | Behaviour |
|------|-----------|
| `IMMEDIATE` | Default. The tool run is created and executed inline. |
| `SCHEDULED` | The tool run row is created immediately, then handed to a **durable Temporal timer**; the node returns `OperationStatus.SCHEDULED` with `schedule_id` and `run_at`. |

Scheduling is configured per node, **not** decided by the LLM:

```json
{
  "scheduling": {
    "mode": "scheduled",
    "delay_seconds": 3600,
    "run_at_param": "execute_at",
    "tool_names": ["createExpense"]
  }
}
```

- `delay_seconds` — fixed offset from now.
- `run_at_param` — reads an absolute timestamp from the operation's LLM-filled params. The value must be timezone-aware and in the future; a **past or malformed `run_at` fails the node** rather than executing early.
- `tool_names` — restricts scheduling to named tools; unlisted tools stay `IMMEDIATE`.

An invalid `scheduling` block raises `DomainValidationException`. If no `ToolRunSchedulerPort` is wired, the node returns `tool_scheduler_unavailable` — it deliberately does **not** fall back to firing the side effect immediately. See [Durable execution](../../durable-execution.md).

### Retry passes

When a `LOOP` edge routes back into this node from `ToolErrorHandlerNode`, the node reads `retry_operation_ids` from state and re-executes **only those operations**. Results already final are carried forward from `finalized_results`, merged by `operation_id`, and the selection is cleared so the next pass is unfiltered.

This matters because the idempotency key embeds `current_node_run_id`, which changes per loop iteration — without the selection, an operation that already succeeded would be executed again on every retry. Runnable example: `examples/tool_retry_loop.py`.

## `ToolErrorHandlerNode`

- **`NodeExecutor`**, no constructor dependencies.
- Reads **`ToolExecutor`** outputs from state, applies **retry** bookkeeping (`retry_counts`, `max_retries`), normalizes legacy `result` vs `results` keys, produces finalized operation statuses (`OperationStatus`).
- Publishes **`retry_operation_ids`** and **`finalized_results`** into `next_state` (not only into `data`), which is what makes the selective retry above work.
- Sets `fallback_required` when retries are exhausted, which is the signal an edge uses to route into `HumanFallback`.

## `MemoryCommitNode`

The module defines a **concrete class** with `node_type`, `side_effect`, `deterministic`, and `execute` — it does **not** inherit `NodeExecutor` in source; **`NodeRegistry`** injects `memory_write_service` and `execution_repository` via a generated subclass (same pattern as other wired nodes).

Prepares **memory write** payloads using **`data_merge` rules** against `NODE_OUTPUTS_BY_NODE_ID_KEY`, optional **`literal_overlay`**, then calls **`MemoryWriteServicePort`** (see the module for `MemoryCommitMergeErrorCode`).

### Persistence outcomes

The node reports what actually happened rather than assuming success. `data` carries `persisted` (bool) and a `reason_code`:

| `reason_code` | Node status | Meaning |
|---------------|-------------|---------|
| `memory_commit_persisted` | `SUCCESS` | The item reached the durable store. |
| `memory_commit_write_not_allowed` | `SUCCESS` | The node definition has `allow_memory_write = false`. A deliberate skip is not a failure. |
| `memory_commit_writer_unavailable` | `SUCCESS` | No `MemoryWriteServicePort` wired (degraded deployment). |
| `memory_commit_node_not_found` | `ERROR` | The node id did not resolve. |
| `memory_commit_invalid_node_id` | `ERROR` | The node id was malformed. |
| `memory_commit_write_failed` | `ERROR` | A write was attempted and the store rejected it; `detail` carries the reason. |

> **Session memory vs durable memory.** `NodeResult.memory` always advances — that is this node's contract for the graph. `persisted` refers **only** to the durable store. A `SUCCESS` status with `persisted: false` is a real and expected state.

Runnable example: `examples/memory_commit_outcomes.py`.

## Related

- [Runtime executor](../runtime-executor.md) — state keys and terminal handling
- [LLM moderation](../../../LLM/resilience-and-moderation.md) — moderation provider stack (distinct from this node’s port)
