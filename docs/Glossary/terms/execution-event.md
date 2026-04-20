# Execution event

## Definition

An **execution event** is an **append-only** runtime record describing what happened during a [Flow run](flow-run.md): node transitions, tool outcomes, errors, and observability hooks. It supports auditing and tracing (e.g. alongside Langfuse spans).

## What it is not

- Not an [Authoring event](authoring-event.md) (design-time audit).
- Not a replacement for external APM traces: it is domain-level fact storage.

## Code

- `src/domain/execution/` (event emission and persistence paths)
- Tracing adapter: `src/adapters/observability/langfuse_runtime_tracer.py`

## Persistence

- `execution_event`. See [persistence tables](../persistence-tables.md).

## Related

- [Flow run](flow-run.md)
- [Develop: system events reference](../../Develop/system-events-reference.md) — full `ExecutionEventType` catalogue
- [Develop: tracing and cost](../../Develop/tracing-and-cost.md)
