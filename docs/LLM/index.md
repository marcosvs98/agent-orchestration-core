# LLM domain services

This section documents **inference orchestration** and supporting services under `src/domain/llm/`: how prompts become provider calls, how **layered inference** (semantic cache → SLM → primary LLM) is ordered, and how **governance** (guardrails, circuit breaker, budgets) interacts with execution.

## Package map

| Area | Role | Path |
|------|------|------|
| **Services** | Orchestration and side effects (cache, executor, context, moderation) | `src/domain/llm/services/` |
| **Ports** | Contracts (`LLMExecutorPort`, `LLMProviderPort`, `ModerationProviderPort`, …) | `src/domain/llm/ports/` |
| **Schemas** | Requests, results, cache policy, provider selection | `src/domain/llm/schemas/` |
| **Adapters** | Concrete providers (OpenAI, SLM local, …) | `src/domain/llm/adapters/` |

Execution graph code that **calls** the LLM stack lives under `src/domain/execution/` (for example `graph_runtime/nodes/_llm_base.py`). Domain LLM services do not own the graph; they implement ports consumed at runtime.

## Reading order

1. **[Layered inference](layered-inference.md)** — `LayeredInferenceOrchestrator`: cache → SLM → LLM, escalation, persist.
2. **[LLM executor](llm-executor.md)** — `LLMExecutor`: selection, factory, `infer`, guardrails, events, post-call policy checks.
3. **[Context builder](context-builder.md)** — `ContextBuilder`: template context for prompts (persona, memory, RAG activation); not the same as layered inference.
4. **[Providers and selection](providers-and-selection.md)** — `LLMProviderSelector`, `LLMProviderFactory`, tenant config and `llm_pricing`.
5. **[Semantic cache](semantic-cache.md)** — `SemanticCacheService`, embeddings, `semantic_answer_cache`.
6. **[Structured output and budget](structured-output-and-budget.md)** — `CompletionBudgetPolicy`, `StructuredOutputSchemaComposer`.
7. **[Resilience and moderation](resilience-and-moderation.md)** — `CircuitBreaker`, moderation orchestration.

## Related documentation

- [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md) — end-to-end cost, layered inference summary, caches.
- [Tracing and cost](../Develop/tracing-and-cost.md) — observability.
- [System events reference](../Develop/system-events-reference.md) — `LLMCall*` and guardrail events.
- [RAG overview](../RAG/index.md) — retrieval and embedding (distinct from chat completion, but shares `EmbeddingExecutor` for semantic cache embeddings).
- [Persistence tables](../Glossary/persistence-tables.md) — `semantic_answer_cache` and governance tables.
