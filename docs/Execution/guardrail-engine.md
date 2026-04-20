# Guardrail engine

`GuardrailEngine` (`src/domain/execution/services/guardrails/guardrail_engine.py`) enforces **LLM governance** policies that depend on **Redis-backed** counters and optional **`CostEngine`** projections: spend and call counts **per flow run** and **per tenant**, soft/hard latency, and related decisions surfaced as `GuardrailDecision` (`BLOCK`, `DEGRADE`, etc.).

## Relationship to `LLMExecutor`

The executor calls `guardrail_engine.check_and_reserve` **before** the provider `infer` when `policy_llm` is present, and `record_post_call_cost` **after** a successful LLM completion. Event emission (`GuardrailChecked`, `GuardrailBlocked`, `GuardrailDegraded`) is implemented in **`LLMExecutor`**, not in this file.

For the end-to-end LLM pipeline, event types, and policy fields on `LLMRequest`, see:

- [LLM executor](../LLM/llm-executor.md)
- [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md)

This page avoids duplicating guardrail math; read `check_and_reserve` / `_check_and_reserve_impl` and Redis key helpers in source for exact rules.

## Related

- [Execution service](execution-service.md) — `GuardrailEngine` constructed with the same `RedisAdapter` / `CostEngine` as the rest of the stack
