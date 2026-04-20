# Agent runtime resolver

`AgentRuntimeResolver` (`src/domain/execution/services/graph_runtime/agent_runtime_resolver.py`) resolves a **per-node system prompt** from the **agent version** attached to the node in persistence.

## `resolve_system_prompt(flow_run_id, node_id, state)`

1. Cache key: `"_agent_system_prompt_{node_id}"` in `state` — if present, returns cached value (string or `None`).
2. Otherwise **`get_agent_version_id_by_node_id(node_id)`** via `AgentsRepository`.
3. Loads **`get_agent_version`**, reads `system_prompt` (stripped) or `None`.
4. Stores result on `state` under the same key for subsequent nodes in the run.

Used by **`LLMNodeExecutor`** (`_llm_base.py`) when `agent_runtime_resolver` is configured, to override/augment the system prompt for the LLM call.

## Related

- [LLM node base](nodes/llm-node-base.md)
- [Nodes index](nodes/index.md)
