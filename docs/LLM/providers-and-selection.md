# Providers and selection

Tenant-scoped **provider configuration**, **model alias mapping**, and **pricing** are resolved before each LLM call when the executor is wired with selector + factory.

## `LLMProviderSelector`

`src/domain/llm/services/provider_selector.py`

`select(tenant_id, provider, model_alias)`:

1. **`LLMProviderRepository.get_active_config`** — Fails with `llm_provider_not_active` if missing.
2. **`LLMModelMappingRepository.get_active_mapping`** — Resolves `model_alias` → `provider_model`; fails with `llm_model_mapping_not_found` if missing.
3. **`LLMPricingRepository.get_active_pricing`** — Loads tariff for `provider` + `provider_model`; fails with `llm_pricing_not_found` if missing.

Returns `LLMProviderSelection` (`src/domain/llm/schemas/llm.py`) with `provider`, `provider_model`, `base_url`, and `credential_secret_ref` for adapter construction.

## `LLMProviderFactory`

`src/domain/llm/services/provider_factory.py`

`build(selection: LLMProviderSelection) -> LLMProviderPort`:

- If `selection.provider` is **`OPENAI`**, returns the injected `openai_provider`.
- If **`SLM_LOCAL`**, returns the injected `slm_local_provider`.
- Otherwise raises `ValueError` with `unsupported_provider:...`.

Dependency injection in `ExecutionService` passes `provider_factory=provider_factory.build` into `LLMExecutor`, so each selection yields a **fresh or shared** adapter instance according to how providers are constructed in the container.

## Embeddings

Chat completion uses the factories above. **Query embeddings** for semantic cache use `EmbeddingExecutor` and `OpenAIEmbeddingAdapter` under `src/domain/rag/`; see [Semantic cache](semantic-cache.md) and [Embedding orchestration](../RAG/embedding-orchestration.md) — not the chat provider stack.

## See also

- [LLM executor](llm-executor.md)
- [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md) — `llm_pricing` and `CostEngine`
- [Glossary: persistence](../Glossary/persistence-tables.md) — governance tables backing provider config
