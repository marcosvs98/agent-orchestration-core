# Runtime policy resolver

`RuntimePolicyResolver` (`src/domain/execution/services/runtime_policy_resolver.py`) loads a **`ResolvedRuntimePolicy`** for use when the runtime does **not** embed policy inside a flow snapshot document (legacy graph contract path in `ExecutionService`).

## Precedence

Docstring: **FLOW → TENANT → DEFAULT**.

| Condition | Source | Scope |
|-----------|--------|--------|
| `flow_id` is provided and `get_active_flow_policy` returns a row | `RuntimePolicySource.FLOW` | Flow-scoped definition |
| `flow_id` is **absent** and tenant policy exists | `RuntimePolicySource.TENANT` | Tenant policy row |
| No tenant policy | `RuntimePolicySource.DEFAULT` | `default_policy["policy_definition"]` from the resolver constructor |

When **`flow_id` is provided** and an active **flow** policy exists, the returned `ResolvedRuntimePolicy` carries that definition and `RuntimePolicyScope.FLOW`.

When **`flow_id` is omitted**, the resolver queries **tenant** policy first, then falls back to the **default** definition with `RuntimePolicyScope.TENANT` and `flow_id=None` in the default branch.

## Integration

- `ExecutionService` passes `ResolvedRuntimePolicy` into `RuntimeExecutor.run` as `runtime_policy`.
- The executor copies the policy definition into `ExecutionContext.metadata["runtime_policy"]` so **nodes** and **LLM** code can read `llm`, `memory_retrieval`, `user_context_enrichment`, etc.

## Related

- [Runtime executor](graph-runtime/runtime-executor.md) — where metadata is applied
- [Execution service](execution-service.md) — flow snapshot vs resolver path
