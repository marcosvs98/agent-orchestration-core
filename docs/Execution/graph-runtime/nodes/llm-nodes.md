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

`LLMTaskType.MEMORY_CONTENT_SUMMARIZE`, `state_key_use_value = True`. **Overrides `execute`** — it is size-gated and does not unconditionally call the LLM.

### Config

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `source_node_id` | `str` | *(required)* | Node id whose output is read from `NODE_OUTPUTS_BY_NODE_ID_KEY`. |
| `min_payload_bytes_to_run` | `int` | `1` | The node runs only when the serialized source output is at least this many bytes. |
| `replace_source_output` | `bool` | `false` | When true, the source node's slice in the state snapshot is replaced by the summary. |

### Contract

1. Resolves `source_node_id` in the graph-state snapshot. A missing config key or a missing source output short-circuits — it does **not** fail the run.
2. Serializes the source output and measures it. **Below the threshold it returns without spending a token.**
3. Above the threshold it stages the raw payload under `MEMORY_CONTENT_SUMMARIZE_STAGING_KEY` (which is what the prompt resolver reads), runs the LLM, then **strips the staging key** from the outgoing state so the raw payload does not travel onward.

`data` carries `summarized`, a `reason_code`, and a `compaction` block (`payload_bytes`, `summary_bytes`, `saved_bytes`, `compaction_ratio`). `compaction` is also merged into `metrics` alongside — not over — the LLM `token_usage`.

| `reason_code` | Meaning |
|---------------|---------|
| `context_summarizer_compacted` | The LLM ran and produced a summary. |
| `context_summarizer_below_threshold` | Payload smaller than `min_payload_bytes_to_run`; no LLM call. |
| `context_summarizer_source_output_missing` | `source_node_id` has no output in the snapshot yet. |
| `context_summarizer_source_node_id_missing` | Config did not name a source node. |

`replace_source_output` defaults to **`false`** deliberately: other nodes may read the source node's output by id — the demo graph's `MemoryCommitNode` merges from exactly the node the summarizer targets — so unconditional replacement would break them. Enable it only when nothing downstream needs the raw payload.

> **Scope.** This node bounds payloads carried **in graph state**. It does not bound the provider-side conversation history (see [Token cost and context strategy](../../../Develop/token-cost-and-context-strategy.md)), which grows outside anything this node can reach.

Runnable example: `examples/context_compaction.py`.

## `HumanFallback`

`LLMTaskType.FALLBACK_RESPONSE`, `write_next_state = False`. Optionally creates/updates **human SLA** cases via **`HumanSLAService`** when `current_node_run_id` is set, then delegates to the base LLM path for the user-facing fallback message.

It reads two metadata keys, **both written by `node_step_runner` when an edge routes into this node** — the node itself never has to infer them:

| Metadata key | Written from |
|--------------|--------------|
| `fallback_source_node` | `context.current_node_id` of the node that escalated. |
| `fallback_reason` | `resolve_fallback_reason(...)` — see [Policies and matching](../../../Human-SLA/policies-and-matching.md#how-fallback_reason-is-derived). |

These two strings are the composite key `resolve_policy` matches on, so a wrong or missing value means **no policy is found** and the case is created without one.

See [Human SLA overview](../../../Human-SLA/index.md) and [Cases and service](../../../Human-SLA/cases-and-service.md) for policy matching, case lifecycle, and HTTP API.

## `IntentClassifier`

`LLMTaskType.INTENT_SELECTION`, `PromptIntent.INTENT_TOOL_SELECTION`, `include_available_tools = False`, `write_next_state = True`.

`intent_classifier.py` is **pure configuration**: it subclasses `LLMNodeExecutor` and sets class
attributes only — no `__init__`, no `execute` override. All behaviour comes from the base.

Like the other wired nodes, it is still **not** constructed directly: `NodeRegistry.resolve` returns
a generated `_IntentClassifier` subclass whose `__init__` injects `llm_executor`, `prompt_resolver`,
`tracer`, `agent_runtime_resolver` and `completion_budget_policy`. Instantiating the module class
yourself skips that injection, so use **`registry.resolve(NodeType.IntentClassifier)`** as the entry
point in integration tests (`resources/scripts/examples/nodes/validate_node_intent_and_tools.py`).

Its output shape matters beyond this node: `resolve_fallback_reason` reads `result[0].intent_type`
to distinguish `UNKNOWN_INTENT` from `LOW_CONFIDENCE` when an edge escalates to `HumanFallback` —
see [Policies and matching](../../../Human-SLA/policies-and-matching.md#how-fallback_reason-is-derived).

## Related

- [LLM node base](llm-node-base.md)
- [Node registry](../node-registry.md)
