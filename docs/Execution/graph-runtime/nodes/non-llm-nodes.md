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
- Returns structured **`ToolExecutorOutput`**-style payloads in state (see `schemas/tool_executor.py` and module for error handling).

## `ToolErrorHandlerNode`

- **`NodeExecutor`**, no constructor dependencies.
- Reads **`ToolExecutor`** outputs from state, applies **retry** bookkeeping (`retry_counts`, `max_retries`), normalizes legacy `result` vs `results` keys, produces finalized operation statuses (`OperationStatus`).

## `MemoryCommitNode`

The module defines a **concrete class** with `node_type`, `side_effect`, `deterministic`, and `execute` — it does **not** inherit `NodeExecutor` in source; **`NodeRegistry`** injects `memory_write_service` and `execution_repository` via a generated subclass (same pattern as other wired nodes).

- Prepares **memory write** payloads using **`data_merge` rules** against `NODE_OUTPUTS_BY_NODE_ID_KEY`, optional **`literal_overlay`**, then calls **`MemoryWriteServicePort`** and records execution events via repository on success/failure paths (see full file for `MemoryCommitMergeErrorCode` and persistence semantics).

## Related

- [Runtime executor](../runtime-executor.md) — state keys and terminal handling
- [LLM moderation](../../../LLM/resilience-and-moderation.md) — moderation provider stack (distinct from this node’s port)
