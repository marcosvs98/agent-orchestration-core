# Execution domain services

This section documents runtime **flow execution** in `src/domain/execution/services/`: orchestrating published flows, validating lifecycle transitions, resolving **runtime policy**, compiling **flow graph snapshots** into an **execution plan**, and driving **node** execution with **edge evaluation** and **hooks**.

## Package map

| Area | Role | Path |
|------|------|------|
| **ExecutionService** | Application entry: create/resume runs, compile/cache plan, invoke graph runtime, agent/tool runs | `src/domain/execution/services/execution_service.py` |
| **Agent runtime** | Direct agent executions: context, tool grant, LLM ↔ tool loop, A2A delegation | `src/domain/execution/services/agent_runtime/` |
| **State machines** | Legacy `RunStatus` transitions vs Planning-10 canonical statuses | `src/domain/execution/services/state_machine.py` |
| **Runtime policy** | FLOW / TENANT / DEFAULT resolution (legacy graph path) | `src/domain/execution/services/runtime_policy_resolver.py` |
| **Graph runtime** | Compiler, plan, executor, edges, node registry | `src/domain/execution/services/graph_runtime/` |
| **Observability** | `ExecutionEventHook` implementations (DB events, memory extraction) | `src/domain/execution/services/observability/hooks.py` |
| **Guardrails** | Pre/post LLM limits via Redis + policy | `src/domain/execution/services/guardrails/guardrail_engine.py` |

Ports and repositories live under `src/domain/execution/ports/` and `src/domain/execution/repositories/` (not duplicated here).

## Reading order

1. [Flow lifecycle](flow-lifecycle.md) — high-level run states (existing page).
2. [Execution service](execution-service.md) — `create_flow_run`, `resume_flow_run`, wiring.
3. [Agent runtime](agent-runtime.md) — agent runs, execution-scoped context and tools, A2A.
4. [State machine](state-machine.md) — `ExecutionStateMachine` and `RunLifecycleStateMachine`.
5. [Runtime policy resolver](runtime-policy-resolver.md) — policy precedence.
6. [Observability and hooks](observability-and-hooks.md) — hook pipeline and DB events.
7. [Guardrail engine](guardrail-engine.md) — limits vs `LLMExecutor`.
8. [Graph runtime overview](graph-runtime/index.md) — compiler → plan → executor → nodes.

## Glossary and related docs

- [Flow run](../Glossary/terms/flow-run.md), [execution event](../Glossary/terms/execution-event.md).
- [Runtime vs authoring](../Architecture/runtime-vs-authoring.md).
- [LLM executor](../LLM/llm-executor.md), [tracing and cost](../Develop/tracing-and-cost.md), [system events](../Develop/system-events-reference.md).
