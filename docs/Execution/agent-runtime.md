# Agent runtime

An **Agent** is a persistent, versioned configuration. An **Agent Run** is one execution of that
configuration: it carries its own context, its own tool authorization and its own lifecycle, and
it never mutates the agent it ran.

This page documents the direct-execution path (`POST /core/v1/executions/agent-runs`). The
flow-driven path — where a node's agent binding produces an agent run — is unchanged and
documented under [graph runtime](graph-runtime/index.md); both write to the same `agent_run`
table, distinguished by `origin`.

## The cycle

```text
Agent definition ─┐
Execution context ├─→ prompt parts ─→ LLM ─→ tool calls ─→ tool results ─┐
Tool grant       ─┘                    ▲                                 │
                                       └─────────────────────────────────┘
                                                  bounded by max_iterations
                                       ─→ final output ─→ artifact
```

Each turn is one call to `AgentLLMPort.complete_agent_turn`. If the model answers with tool
calls, the runtime executes them, appends the results to the transcript, and asks again. If it
answers with text and no tool calls, the run finishes with `FINAL_OUTPUT`. If the bound is
reached first, the run finishes with `MAX_ITERATIONS`; it never loops without end.

## Package map

| Area | Role | Path |
|------|------|------|
| **AgentRunService** | Lifecycle: create, execute (sync/async), read, cancel; also the in-process A2A transport | `src/domain/execution/services/agent_run_service.py` |
| **AgentDefinitionResolver** | Loads the agent, active published version, AI execution policy, model, billing policy, tool catalogue | `src/domain/execution/services/agent_runtime/definition.py` |
| **ToolGrantResolver** | Turns the request's tool constraints into the run's frozen authorization | `src/domain/execution/services/agent_runtime/tool_grant.py` |
| **AgentRunContextBuilder** | Assembles the opening transcript with trust levels and provenance | `src/domain/execution/services/agent_runtime/context_builder.py` |
| **AgentToolDispatcher** | Enforces the grant, validates arguments, runs the tool, dispatches delegation | `src/domain/execution/services/agent_runtime/tool_dispatcher.py` |
| **AgentCognitiveLoop** | The bounded LLM ↔ tool cycle, transcript and event persistence | `src/domain/execution/services/agent_runtime/agent_loop.py` |
| **AgentRunRepository** | Runs, messages, events, artifacts | `src/domain/execution/repositories/agent_run_repository.py` |

## Entities

| Concept | Where it lives | Notes |
|---------|----------------|-------|
| Agent | `agent`, `agent_version` | Existing; unchanged |
| Agent Run | `agent_run` | Extended with `tenant_id`, `agent_id`, nullable `node_run_id`, `origin`, delegation links, `context_snapshot`, `tool_grant`, iteration counters, `finish_reason` |
| Context | `agent_run.context_snapshot` | Execution-scoped, frozen at creation |
| Message | `agent_run_message` | Append-only transcript with `role`, `trust_level`, `source` |
| Event | `agent_run_event` | Append-only; reuses `ExecutionEventType` |
| Tool / Tool Call | `tool`, `tool_config` / `tool_run` | Existing tables; `tool_run.tool_call_id` correlates a call to the model's request |
| Artifact | `agent_run_artifact` | A2A `Part` list plus a payload |
| Task / A2A delegation | `agent_delegation` | One row per delegated A2A task |

No parallel run table was introduced: a flow-embedded agent run and a direct one differ only by
`origin` and by whether `node_run_id` is set.

## Execution-scoped context

`context` is a list of `{key, content, description}` items supplied per run. They are recorded on
the run, replayed from the run's own snapshot, and injected as `developer` prompt parts labelled
`caller_supplied` — never merged into the agent version. The agent's published prompt and the
runtime rules stay `trusted_instruction`, so the model is told which text is instruction and
which is data.

## Tool authorization

`tools.allowed_tool_names` selects a subset of the tools the **agent version** is bound to:

- omitted → every bound tool;
- a list → exactly those (an unknown name is rejected at creation with
  `tool_not_bound_to_agent_version`);
- `[]` → none.

The resolved grant is written to `agent_run.tool_grant` and is the only thing the runtime
consults. Three consequences:

1. Only granted tools are described to the model, so an ungranted tool is not even offered.
2. A call for a tool outside the grant is answered with `tool_not_authorized_for_this_run`
   before any `tool_run` row is created — the tool is never reached.
3. Re-executing a run replays the frozen grant, so publishing a new agent version mid-run cannot
   widen what that run may call.

Arguments are validated against the tool config's `request_schema` before execution; an invalid
call becomes a result the model can correct from, not a side effect.

Execution itself goes through the existing tool runtime
(`ToolOrchestrator.execute_agent_tool_run`), which shares transport, secret resolution and
response validation with the flow path and with the tenant MCP server. Tool function names use
the same convention the MCP server exposes, so a tool keeps one name on both surfaces.

## LLM

`AgentLLMPort` (`src/domain/llm/ports/agent_llm.py`) is a single tool-capable turn: messages and
tool definitions in, text and/or tool calls out. It is deliberately separate from
`LLMProviderPort.infer`, which returns structured JSON for a graph node and has no notion of a
tool call.

`OpenAIProviderAdapter` implements it over the Responses API. The runtime depends on the port,
never on the adapter; the model comes from the agent version's AI execution policy, so provider
and model selection stay where the rest of the platform puts them.

Every turn is written to `llm_usage_ledger` with `agent_run_id`, so agent-run spend lands in the
same ledger as graph execution.

## A2A

Agent-to-agent work uses the [Agent2Agent protocol](https://a2a-protocol.org/) vocabulary —
Agent Card, Task, Message, Part, Artifact, task state — confined to an adaptation layer under
`src/domain/agents/`:

| Piece | Path |
|-------|------|
| Protocol objects | `src/domain/agents/schemas/a2a.py` |
| Translator (AOC ↔ A2A) | `src/domain/agents/services/a2a_translator.py` |
| Delegation lifecycle | `src/domain/agents/services/a2a_delegation_service.py` |
| Agent Card | `src/domain/agents/services/agent_card_service.py` |
| Transport port | `src/domain/agents/ports/agent_task_runner.py` |
| Server (card + JSON-RPC) | `src/domain/agents/controllers/a2a_controller.py` |

Nothing in the orchestration domain imports A2A types directly; the runtime asks for a
delegation and receives a domain result.

### Delegating

A run may delegate only if its grant says so:

```json
{"tools": {"allow_agent_delegation": true, "delegate_agent_ids": ["<agent-b-id>"]}}
```

That adds a `delegate_to_agent` tool whose `agent_id` is constrained to the listed agents, and the
constraint is re-checked at dispatch. Delegation then:

1. mints an A2A `taskId`, and a `contextId` derived from the root run so a whole tree shares one
   context;
2. builds an A2A `Message` (`role: user`) from the instruction and payload;
3. writes an `agent_delegation` row in `submitted`;
4. hands the task to an `AgentTaskRunnerPort`. In process, that is `AgentRunService`, which
   creates **a second agent run** for agent B with `origin=A2A_DELEGATION`,
   `parent_agent_run_id`, the shared `root_agent_run_id`, and `delegation_depth + 1`;
5. records the terminal `Task` (state, history, artifacts) back onto the delegation row.

Agent B has its own run id, context, grant, transcript, events, artifacts and spend. Agent A
receives the result as a tool result and continues its own loop. Depth is bounded
(`MAX_DELEGATION_DEPTH`), and B cannot delegate further unless its own run grants it.

Because the transport is a port, a remote peer would be a second implementation speaking
JSON-RPC `message/send` — the orchestration domain would not change.

### Serving

- `GET /core/v1/agents/{agent_id}/agent-card` — the agent's A2A Agent Card, with skills derived
  from the tools its active version is bound to.
- `POST /core/v1/agents/{agent_id}/a2a` — JSON-RPC 2.0: `message/send`, `tasks/get`,
  `tasks/cancel`. A submitted task becomes an ordinary agent run, so it gets the same lifecycle,
  grant and transcript as one submitted natively; the task id is the agent run id.

## HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/core/v1/executions/agent-runs` | Start a run. Requires `Idempotency-Key`. `?wait=true` (default) blocks until terminal and answers `201`; `?wait=false` answers `202` and executes in the background. |
| `GET` | `/core/v1/executions/agent-runs` | List runs; filter by `agent_id`, `flow_run_id`, `root_agent_run_id`, `parent_agent_run_id`. Covers both direct and flow-embedded runs, and replaces the plane's earlier `GET /core/v1/executions/agent-runs`. |
| `GET` | `/core/v1/executions/agent-runs/{agent_run_id}` | Run detail: context snapshot, tool grant, transcript, events, tool calls, artifacts, delegations. |
| `POST` | `/core/v1/executions/agent-runs/{agent_run_id}:cancel` | Cancel a non-terminal run. |

Scopes: `execution:agent_run:create`, `execution:agent_runs:list`, `execution:agent_run:get`,
`execution:agent_run:cancel`. `tenant_id` always comes from the JWT.

### Request

```json
{
  "agent_id": "…",
  "instruction": "Summarise this quarter's churn drivers and propose two actions.",
  "payload": {"quarter": "2026-Q2"},
  "context": [
    {"key": "account", "content": "Enterprise plan, 340 seats, renewal in 60 days."}
  ],
  "tools": {"allowed_tool_names": ["list_user_transactions"]},
  "max_iterations": 6
}
```

`instruction` is the task. `payload` is structured input. `context` is execution-scoped context.
`tools` is the authorization for this execution only. `max_iterations` bounds the cycle
(default 8, ceiling 25).

## Asynchronous execution and streaming

`?wait=false` returns `202` immediately and runs the loop as a background task; callers poll the
detail endpoint, whose events and transcript grow as the run proceeds. Cancellation interrupts
the in-flight task when it belongs to the process that accepted the run, and always marks the
run cancelled.

Two things are deliberately left open for streaming and genuinely long-running work: the
transcript and events are written turn by turn (so a stream can be built from them without
changing the runtime), and the loop is a plain service call (so it can be moved behind the
existing Temporal workflow engine without changing the contract).

## Related

- [Quickstart](../Get-Started/quickstart-tenant-and-resources.md) — configure a tenant and call
  this surface with `curl`, end to end.
- [Execution service](execution-service.md) — flow runs and the flow-embedded agent run path.
- [Graph runtime](graph-runtime/index.md) — node-driven execution.
- [Agents](../Agents/index.md) — agent and agent version authoring.
- [Tools](../Tools/index.md) — tool configs and bindings.
- [Tracing and cost](../Develop/tracing-and-cost.md) — where agent-run spend lands.
