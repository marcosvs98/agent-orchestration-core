# Node registry

`NodeRegistry` (`src/domain/execution/services/graph_runtime/registry.py`) maps **`NodeType` string** (from the graph snapshot) to a **concrete executor class**, and supplies **dependency injection** for constructors that need services (LLM, tools, memory, moderation, SLA).

## Static map

`_registry` keys include:

`ContentModeration`, `ToolResolver`, `IntentClassifier`, `ToolInputFiller`, `ToolExecutor`, `QueryClarifier`, `ToolErrorHandlerNode`, `ResponseBuilder`, `HumanFallback`, `MemoryCommitNode`, `ContextSummarizer`

## `resolve(node_type) -> Type | None`

Returns a **subclass** in many cases:

- **`ToolResolver`** — inner class `_ToolResolver` whose `__init__` injects `llm_executor`, `prompt_resolver`, `tool_catalog_retriever`, `agents_repository`, `tool_catalog_indexer`, optional `agent_runtime_resolver`, `completion_budget_policy`. Raises if catalog or LLM deps missing.
- **`IntentClassifier`**, **`ToolInputFiller`**, **`QueryClarifier`**, **`ResponseBuilder`**, **`ContextSummarizer`** — inject LLM stack + optional budget policy.
- **`ToolExecutor`** — `tool_orchestrator`, `execution_repository`.
- **`MemoryCommitNode`** — `memory_write_service`, `execution_repository`.
- **`ContentModeration`** — requires `llm_moderation_provider`.
- **`HumanFallback`** — `human_sla_service` optional; LLM + prompt deps.

Node types **without** a dedicated `if node_type == ...` branch (for example **`ToolErrorHandlerNode`**) return the **registry class directly** — their constructors take no injected services (`ToolErrorHandlerNode.__init__` is empty).

## Construction

`ExecutionService` builds a single `NodeRegistry` with the same long-lived dependencies as the rest of the service; **`RuntimeExecutor`** receives `registry` or constructs `NodeRegistry(tracer=tracer)` by default.

## Related

- [Nodes index](nodes/index.md)
- [Agent runtime resolver](agent-runtime-resolver.md)
