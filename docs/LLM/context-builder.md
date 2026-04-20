# Context builder

`ContextBuilder` (`src/domain/llm/services/context_builder.py`) builds **template context** for prompt resolution: the structured dictionary passed into the prompt system (persona, tools, memory layers, config flags). It is **not** the same component as [Layered inference](layered-inference.md); layered inference decides **which provider and cache path** run for an `LLMRequest`, while `ContextBuilder` prepares **what goes into the prompt** for nodes that eventually call `LLMExecutor` (directly or via orchestrator).

## Responsibilities

- **Persona** — Loads `PersonaConfig` from `AgentsRepository` for `agent_version_id`.
- **Tools** — Coerces `available_tools` from `ExecutionContext` into models used in template `meta`.
- **Layered memory and RAG** — When ports are configured:
  - `MemoryRetrievalServicePort` supplies tenant knowledge, structured user memory, vector memory, and session context according to `MemoryRetrievalConfig` from `runtime_policy.memory_retrieval`.
  - `RagActivationService` gates whether tenant knowledge retrieval runs (`decide` per scope, task type, flags, `rag_config_id`, etc.).
  - `RuntimeContextLayerPolicy` combines policy with execution state to produce a `LayerUsageDecision` (which layers are allowed).
- **User context enrichment gating** — Reads `runtime_policy.user_context_enrichment` and may restrict layers until a user-context read gate in state is satisfied (see `USER_CONTEXT_READ_GATE_STATE_KEY` usage in source).

Main public entry: `build_template_context` (async), which merges `meta`, `persona`, `config`, `input`, `layers`, and related fields from `ExecutionContext`, `input_payload`, and `task_type`.

## Relationship to execution graph

Graph nodes such as `LLMNodeExecutor` (`src/domain/execution/services/graph_runtime/nodes/_llm_base.py`) resolve prompts through `PromptResolver` using execution context; that path can consume output from **prior nodes** (for example tool selection). `ContextBuilder` feeds the **prompt template** side (what the model should see), while node executors assemble `LLMRequest` and call `llm_executor.execute_llm`.

## See also

- [LLM executor](llm-executor.md)
- [RAG overview](../RAG/index.md) — retrieval stack that may populate context layers
- [Token cost and context strategy](../Develop/token-cost-and-context-strategy.md) — context growth and shrinkage
