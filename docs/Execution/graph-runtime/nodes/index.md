# Graph runtime nodes

Concrete node implementations live in `src/domain/execution/services/graph_runtime/nodes/`. Each node implements the **`NodeExecutor`** protocol (`execute(context, config) -> NodeResult`) declared in `types.py`. LLM-backed nodes subclass **`LLMNodeExecutor`** (`_llm_base.py`).

## Taxonomy

| Node type | Module | Base | Notable dependencies |
|-----------|--------|------|----------------------|
| `ToolResolver` | `tool_resolver.py` | `LLMNodeExecutor` | `LLMExecutorPort`, `PromptResolver`, tool catalog retriever/indexer, `AgentsRepository` |
| `IntentClassifier` | `intent_classifier.py` | `LLMNodeExecutor` (class attributes only) | LLM + prompts + budget policy |
| `ToolInputFiller` | `tool_input_filler.py` | `LLMNodeExecutor` | LLM + prompts + budget policy |
| `QueryClarifier` | `query_clarifier.py` | `LLMNodeExecutor` | LLM + prompts |
| `ResponseBuilder` | `response_builder.py` | `LLMNodeExecutor` | LLM + prompts |
| `ContextSummarizer` | `context_summarizer.py` | `LLMNodeExecutor` (overrides `execute`) | LLM + prompts |
| `HumanFallback` | `human_fallback.py` | `LLMNodeExecutor` | LLM + optional `HumanSLAService` |
| `ContentModeration` | `content_moderation.py` | `NodeExecutor` | `ModerationProviderPort` |
| `ToolExecutor` | `tool_executor.py` | `NodeExecutor` | `ToolOrchestrator`, `ExecutionRepository`, optional `ToolRunSchedulerPort` |
| `ToolErrorHandlerNode` | `tool_error_handler.py` | `NodeExecutor` | None (state-only) |
| `MemoryCommitNode` | `memory_commit.py` | *(class with `execute`; registry injects services)* | `MemoryWriteServicePort`, `ExecutionRepository` |

## Behavioural tests

BDD and unit tests under `tests/bdd/graph_runtime/` and `tests/unit/` exercise compiler, registry, and node contracts — use them when changing semantics.

## Detail pages

- [LLM node base](llm-node-base.md)
- [LLM-backed nodes](llm-nodes.md)
- [Non-LLM nodes](non-llm-nodes.md)
- [Shared utilities](shared-utilities.md)
