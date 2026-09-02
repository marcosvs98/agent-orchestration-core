# LLM executor

`LLMExecutor` (`src/domain/llm/services/llm_executor.py`) is the primary implementation of `LLMExecutorPort`. It turns an `LLMRequest` plus runtime identifiers into a provider `infer` call, applies **JSON Schema** validation on input and output, runs **guardrails** when configured, attributes **USD cost** via `CostEngine`, enforces **post-call policy** limits, and emits **execution events** for observability and audit.

## Dependencies (constructor)

| Dependency | Role |
|------------|------|
| `ExecutionRepository` | Append `LLMCall*` and related execution events |
| `LLMProviderPort` (optional) | Default provider when selector/factory are not used |
| `CircuitBreaker` | `ensure_closed` before call; `record_success` / `record_failure` after |
| `CostEngine` | Computes `cost_usd` from `token_usage` and `llm_pricing` |
| `LLMProviderSelector` + `provider_factory` | Resolve tenant model alias → `provider_model` and concrete provider instance |
| `GuardrailEngine` | Pre-call checks and post-call cost recording when `policy_llm` is present |
| `RuntimeTracerPort` | OpenTelemetry spans (chain, generation, evaluator, guardrail) |

`provider_factory` is typically `LLMProviderFactory.build` (see [Providers and selection](providers-and-selection.md)).

## High-level pipeline

1. **Provider resolution** — If `provider_selector` and `provider_factory` are set, `select` loads tenant provider config, model mapping, and pricing; the factory returns the `LLMProviderPort` for `OPENAI` or `SLM_LOCAL`. The request’s `model_alias` is updated to the resolved `provider_model`.
2. **Circuit breaker** — `ensure_closed` on scope `"{provider}:{tenant_id}"`; open circuit raises `DomainValidationException` with `llm_circuit_breaker_open` (when Redis state indicates open and silent mode does not swallow).
3. **`LLMCallStarted` event** — Persisted before the main work.
4. **Chain span** — Named from `task_type` (lowercased); includes prompt payload metadata for tracing.
5. **Input validation** — `_validate_schema` on `user_payload` / `input_payload` / minimal user message or prompt against `request.input_schema`.
6. **Guardrails** — When `guardrail_engine` and `policy_llm` are set: `check_and_reserve`. **BLOCK** raises `guardrail_blocked` after emitting `GuardrailChecked` + `GuardrailBlocked`. **DEGRADE** may override `model_alias`, rebuild provider selection, emit `GuardrailDegraded`, and set `max_latency_ms` from overrides.
7. **Generation** — `provider_instance.infer(request, on_delta=...)`. Pipeline latency may be filled from monotonic clock if missing.
8. **Cost** — `CostEngine.compute_cost` when configured.
9. **Output normalization** — String outputs parsed with `orjson`; single-key `{"content": "<json string>"}` unwraps to a dict.
10. **Output validation** — `_validate_schema` on parsed output vs `request.output_schema`.
11. **Policy enforcement** — `_enforce_policy` (see below).
12. **Success path** — `LLMCallCompleted`, optional `NodePromptExecuted` when prompt version/hash present, `guardrail_engine.record_post_call_cost`, `circuit_breaker.record_success`.

On any exception after the try block for the provider call, `LLMCallFailed` is emitted and the circuit breaker records failure.

## JSON Schema and errors

- Input failures use message code `llm_input_invalid`.
- Output failures use `llm_output_invalid`.
- JSON parse failures use `llm_output_json_parse_error`.

Validation runs under a traced `evaluator.schema_validation` span.

## Guardrail events

Besides `GuardrailChecked` / `GuardrailBlocked` / `GuardrailDegraded`, blocked execution stops before `infer`.

## Policy enforcement (`_enforce_policy`)

After a successful schema-validated result:

- **`max_tokens`** — Compares completion token count from `token_usage` (`completion_tokens`, `output_tokens`, or `total_tokens` fallback) to `request.max_tokens`; raises `llm_policy_max_tokens_exceeded` if exceeded.
- **`max_cost_usd`** — Raises `llm_policy_cost_exceeded` when `result.cost_usd` exceeds the cap.
- **`max_latency_ms`** — Raises `llm_policy_latency_exceeded` when `result.latency_ms` exceeds the cap. Enforcement is live; it had previously been disabled with the `raise` commented out behind a debug `print`, so treat older notes saying otherwise as stale.

## Cost accounting

`CostEngine` combines provider-reported `token_usage` with active rows from `llm_pricing`. For product-level pricing strategy, budgets, and caches, see [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md) rather than duplicating tariff detail here.

## Execution events

Relevant event types (payload shapes in `src/domain/execution/services/observability/event_payloads.py`):

- `LLMCallStarted`, `LLMCallCompleted`, `LLMCallFailed`
- `GuardrailChecked`, `GuardrailBlocked`, `GuardrailDegraded` (when guardrails run)
- `NodePromptExecuted` when `prompt_version` and `prompt_frozen_hash` are set

Full catalogue: [System events reference](../Develop/system-events-reference.md).

## Tracing

Spans include `domain.llm.llm_executor.select_provider`, `domain.llm.llm_executor.circuit_breaker_check`, `domain.llm.llm_executor.<task>`, and `domain.llm.llm_executor.infer.<task>`. See [Tracing and cost](../Develop/tracing-and-cost.md).

## See also

- [Layered inference](layered-inference.md)
- [Structured output and budget](structured-output-and-budget.md) — where `max_tokens` may be computed **before** `LLMExecutor` (graph nodes)
