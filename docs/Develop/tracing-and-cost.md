# Tracing and cost

This page is the **entry point for observability**: how traces are emitted and where to look in Langfuse. For **how the runtime controls token spend, context size, caches, and layered inference** — including where to read costs in Langfuse vs pricing tables vs policy limits — use the canonical guide **[Token cost and context strategy](token-cost-and-context-strategy.md)**.

## Langfuse

Runtime tracing integrates with **Langfuse** via `src/adapters/observability/langfuse_runtime_tracer.py`, behind `RuntimeTracerPort`. Domain code should depend on the port, not on Langfuse SDK types directly.

Spans typically cover LLM calls, retrieval, and tool execution. See also [Execution event](../Glossary/terms/execution-event.md).

## Cost

LLM and embedding usage flows through domain services that apply **governance and pricing** hooks (`llm_pricing`, provider config). Exact call sites vary by feature; start from `src/domain/llm/` and `src/domain/rag/` when auditing cost paths. **Narrative and operator steps:** [Token cost and context strategy](token-cost-and-context-strategy.md).

## Related

- [Token cost and context strategy](token-cost-and-context-strategy.md) — layered inference, budgets, RAG/context, and how to consult costs
- [Documentation map (AI)](../AI/documentation-map.md)
- Repository `DEVELOPMENT.md` for local runbook commands
