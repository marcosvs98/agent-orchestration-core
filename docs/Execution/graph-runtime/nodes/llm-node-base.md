# LLM node base

`LLMNodeExecutor` (`src/domain/execution/services/graph_runtime/nodes/_llm_base.py`) provides the shared path for nodes that call **`LLMExecutorPort.execute_llm`**.

## Responsibilities

- Resolve prompts via **`PromptResolver`** (`resolve` with `intent`, `ExecutionContext`, `node_id`, and optionally `node_type` depending on `resolve_prompt_passes_node_type`).
- Optionally merge **agent system prompt** from **`AgentRuntimeResolver.resolve_system_prompt`** when configured.
- Build **`LLMRequest`** with `input_schema` / `output_schema` from resolved prompt or config, **`LLMTaskType`** and **`PromptIntent`** from the concrete subclass, `model_alias` and policy from `runtime_policy.llm` / node `llm` config.
- Apply **`CompletionBudgetPolicy.compute_max_tokens`** when an output schema exists and the policy port is configured (see [Structured output and budget](../../../LLM/structured-output-and-budget.md)).
- Invoke **`llm_executor.execute_llm`** with `policy_llm`, streaming callback when eligible.
- Return **`NodeResult`** with status from subclass (`result_status`), merge output into `next_state` when `write_next_state` is true (keyed by `node_type` or its value per `state_key_use_value`).

## Class attributes (subclasses)

Subclasses set: `node_type`, `llm_task`, `prompt_intent`, `resolve_prompt_passes_node_type`, `include_available_tools`, `result_status`, `write_next_state`, `state_key_use_value`, optional `json_schema_name`.

## Related

- [LLM executor](../../../LLM/llm-executor.md)
- [Agent runtime resolver](../agent-runtime-resolver.md)
- [LLM nodes](llm-nodes.md)
