# Resilience and moderation

## Circuit breaker

`CircuitBreaker` (`src/domain/llm/services/circuit_breaker.py`) uses Redis to track failures per **scope** (`cb:llm:{scope}` with `scope = "{provider}:{tenant_id}"` from `LLMExecutor`).

- **`ensure_closed`** — Before an LLM call: if Redis reports `state == "open"`, raises `DomainValidationException` with `llm_circuit_breaker_open` (in **silent** mode, some Redis errors are swallowed and the call proceeds).
- **`record_failure`** — Increments a counter with TTL; when count reaches `failure_threshold` (default 5) within `window_seconds` (default 60), sets the key to open state.
- **`record_success`** — Called after a successful completion path in `LLMExecutor` (resets / records success per implementation in the same file).

For the full interaction with `LLMExecutor`, see [LLM executor](llm-executor.md).

## Moderation orchestration

`ModerationOrchestrationService` (`src/domain/llm/services/moderation_orchestration_service.py`) implements `ModerationProviderPort` by delegating to injected **SLM** and/or **OpenAI** moderation adapters.

- **`ModerationProviderSelector`** maps config keys `primary` / `fallback` (or legacy `primary_provider`) to provider names (`SLM`, `SLM_LOCAL`, `OPENAI`) and returns an ordered list of `(provider, cfg)` pairs.
- **`moderate(text, config)`** merges `default_config` with per-call config, tries each provider in order, merges top-level keys like `prompt_key`, `output_schema`, `temperature`, `max_tokens` into provider cfg, and returns the first successful `ModerationResult`. On repeated failures, may return `ModerationResult(flagged=False, categories={})`.

This page stays at **orchestration** level; provider-specific moderation behaviour lives under `src/domain/llm/adapters/` and ports.

## See also

- [LLM executor](llm-executor.md) — guardrails distinct from moderation (different engine and events)
- Domain ports: `src/domain/llm/ports/moderation_provider.py`
