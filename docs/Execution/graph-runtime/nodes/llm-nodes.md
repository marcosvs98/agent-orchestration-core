# LLM-backed nodes

These nodes use **`LLMNodeExecutor`** except where noted. Source: `src/domain/execution/services/graph_runtime/nodes/`.

## `ToolResolver`

`LLMTaskType.TOOL_SELECTION`, includes **available tools** in prompt resolution (`include_available_tools = True`). Loads catalog documents via **`ToolCatalogRetriever`** / indexer, may run semantic selection and LLM fallback (see module for orchestration). Requires registry injection of catalog + agents repositories.

## `ToolInputFiller`

Fills tool parameters after selection; uses LLM with schemas from prompt/config (`LLMTaskType` and intent per file).

## `QueryClarifier`

Clarifies user input when intents/tools are ambiguous (`QueryClarifier` registry branch shares LLM injection with other prompt-driven nodes).

## `ResponseBuilder`

`LLMTaskType.RESPONSE_RENDER` — final natural-language response generation; terminal node type in the compiler.

## `ContextSummarizer`

`LLMTaskType.MEMORY_CONTENT_SUMMARIZE`, `state_key_use_value = True`. The `execute` method may delegate to the base implementation; verify the current file for any overrides.

## `HumanFallback`

`LLMTaskType.FALLBACK_RESPONSE`, `write_next_state = False`. Optionally creates/updates **human SLA** cases via **`HumanSLAService`** when `current_node_run_id` is set, using metadata such as `fallback_reason`. Then delegates to the base LLM path for the user-facing fallback message.

See [Human SLA overview](../../../Human-SLA/index.md) and [Cases and service](../../../Human-SLA/cases-and-service.md) for policy matching, case lifecycle, and HTTP API.

## `IntentClassifier` (metadata-only module class)

The file `intent_classifier.py` defines a **bare class** with only **class attributes** (`node_type`, `llm_task`, `prompt_intent`, flags) and **does not** inherit `LLMNodeExecutor` in source.

At runtime, **`NodeRegistry.resolve`** builds a **subclass** `_IntentClassifier` that calls `super().__init__(llm_executor=..., prompt_resolver=..., ...)` — the effective MRO depends on that dynamic subclass. For accurate behaviour, treat **`registry.resolve(NodeType.IntentClassifier)`** as the callable entry point in integration tests (`resources/scripts/examples/nodes/validate_node_intent_and_tools.py`).

Do not document inheritance that is not literally present in `intent_classifier.py` without noting the registry indirection.

## Related

- [LLM node base](llm-node-base.md)
- [Node registry](../node-registry.md)
