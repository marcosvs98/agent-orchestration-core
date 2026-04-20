# Structured output and budget

## `CompletionBudgetPolicy`

`src/domain/llm/services/completion_budget_policy.py`

Computes a recommended **`max_tokens`** for structured JSON outputs from the serialized **output JSON Schema** using **tiktoken** encoding `cl100k_base`.

`compute_max_tokens(provider_model, user_message, output_schema, policy_max, completion_budget)`:

- Serializes `output_schema` with `orjson` (empty object if none).
- Token-counts the schema string; applies `schema_factor` (default **1.2**), `safety_margin` (default **16**), and `floor` (default **32**). Overrides can be passed via `completion_budget` dict.
- Caps by `policy_max` when it is a positive integer.

### Where it runs

This class is **not** invoked inside `LLMExecutor`. Graph runtime injects it into `LLMNodeExecutor` (`src/domain/execution/services/graph_runtime/nodes/_llm_base.py`): when `completion_budget_policy` is set **and** `output_schema` is non-empty, `compute_max_tokens` sets `LLMRequest.max_tokens`; otherwise the ceiling comes from node config / `runtime_policy.llm` only.

## `StructuredOutputSchemaComposer`

`src/domain/llm/services/structured_output_schema_composer.py`

Merges **tool request schema** into prompt **output schema** for **slot filling** so structured outputs can include strict `params` aligned with OpenAPI tool definitions.

- **`compose_for_slot_filling(execution_context, prompt_output_schema)`** — If `extract_tool_config_uuid_from_execution_context` returns a UUID, loads tool config via `ToolsRepository.get_tool_config` and reads `config_mapping["request_schema"]`. Deep-copies the prompt schema, locates the slot-filler `result.items` schema, and injects **`params`** from `build_strict_slot_params_schema`.
- **`extract_tool_config_uuid_from_execution_context`** — Reads `ToolResolver` node output: first row’s `selected_tool.tool_config_id`.
- **`build_strict_slot_params_schema`** — Builds an object schema with `additionalProperties: false` and `required` listing **all** property keys (OpenAPI optional parameters become `anyOf` with `null` via `_optional_param_schema_allowing_null` to satisfy strict structured output rules).
- **`apply_strict_required_keys_to_object_schema`** — Sets `required` to all keys in `properties` and `additionalProperties: false` for nested objects (e.g. `missing_fields.items`).

## See also

- [LLM executor](llm-executor.md) — JSON Schema validation on `LLMRequest.output_schema`
- [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md) — output token budget overview
