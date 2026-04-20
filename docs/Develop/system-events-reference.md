# System events reference

This page lists **canonical event names** you can rely on when integrating with the orchestration runtime: **persisted execution events**, **design-time authoring audit events**, and **Server-Sent Events (SSE)** for live conversation streams. It mirrors a “configuration catalogue” style: one table per surface, with short descriptions.

**Source of truth:** string values are defined as `StrEnum` members in Python. If this page and the code disagree, **trust the enums** (paths below).

## Event surfaces

| Surface | Purpose | Persistence / transport | Canonical enum |
|---------|---------|-------------------------|------------------|
| Execution events | Append-only runtime facts for a [flow run](../Glossary/terms/flow-run.md): nodes, tools, LLM, policy, memory pipeline | Postgres `execution_event` | `ExecutionEventType` — `src/domain/execution/schemas/events.py` |
| Authoring events | Design-time audit: who changed which versioned resource and why | Postgres `authoring_event` | `AuthoringEventType` — `src/domain/governance/schemas/authoring_events.py` |
| Conversation SSE | Live stream to clients during a conversation session | HTTP SSE (not the same row shape as `execution_event`) | `SSEEventType` — `src/domain/conversation/schemas/conversation.py` |

**Note:** execution events and SSE event names **differ in casing and naming** (`FlowStarted` vs `flow_started`). They are related concepts but not identical strings—map by semantics when building UIs.

---

## Execution events

### Row shape (`execution_event`)

Events are stored with a shared envelope plus a JSON `payload` whose keys depend on the emitter (hooks, graph runtime, LLM executor, etc.).

| Column | Description | Type (SQL) |
|--------|-------------|------------|
| `type` | Event type string; must match `ExecutionEventType` values below | `text` |
| `tenant_id` | Tenant scope | `uuid` |
| `user_id` | End-user identifier | `varchar` |
| `session_id` | Conversation session scope | `uuid` |
| `flow_run_id` | Run identifier | `uuid` |
| `correlation_id` | Correlates with logs and traces (e.g. Langfuse) | `uuid` |
| `causation_id` | Optional upstream event correlation | `uuid` or null |
| `event_sequence` | Monotonic ordering within the run | `bigint` |
| `occurred_at` | Timestamp | `timestamptz` |
| `schema_version` | Payload schema evolution | `integer` |
| `payload` | Event-specific details | `jsonb` |
| `node_id` | Optional graph node reference | `uuid` or null |
| `edge_id` | Optional edge reference | `varchar` or null |

See [Persistence tables](../Glossary/persistence-tables.md) and [Execution event](../Glossary/terms/execution-event.md).

### `ExecutionEventType` values

| Event name | Description |
|------------|-------------|
| `FlowStarted` | A flow run has started; execution is entering the runtime pipeline. |
| `FlowRunning` | The run is actively progressing (not waiting on external input). |
| `FlowWaiting` | The run is paused waiting for input or an async continuation. |
| `FlowCompleted` | Terminal success: the flow finished without failure. |
| `FlowFailed` | Terminal failure: the flow ended in an error state. |
| `FlowEscalated` | The run moved to an escalation path (e.g. human or alternate policy). |
| `NodeEntered` | Control reached a node in the graph (pre-start). |
| `NodeStarted` | A node began execution. |
| `NodeSkipped` | A node was not executed (e.g. branch not taken). |
| `NodeCompleted` | A node finished successfully. |
| `NodeFailed` | A node failed during execution. |
| `EdgeEvaluated` | An edge or condition was evaluated for routing. |
| `AgentRunStarted` | An agent invocation started. |
| `AgentRunCompleted` | An agent invocation completed successfully. |
| `AgentRunFailed` | An agent invocation failed. |
| `AgentRunRetried` | A retried agent attempt. |
| `AgentRunAborted` | An agent run was aborted before completion. |
| `ToolInvocationRequested` | A tool call was scheduled or dispatched. |
| `ToolInvocationSucceeded` | Tool call returned success. |
| `ToolInvocationFailed` | Tool call failed. |
| `ToolInvocationTimedOut` | Tool call exceeded its timeout. |
| `ToolInvocationRetried` | Tool call was retried. |
| `LLMCallStarted` | An LLM request began (provider call). |
| `LLMCallCompleted` | An LLM request completed successfully. |
| `LLMCallFailed` | An LLM request failed. |
| `GuardrailChecked` | Safety / policy guardrail was evaluated (allowed path). |
| `GuardrailBlocked` | Guardrail blocked the action or output. |
| `GuardrailDegraded` | Guardrail in degraded mode (e.g. fail-open with warning). |
| `MemoryEmbeddingQueued` | Memory content was queued for embedding. |
| `MemoryEmbeddingStarted` | Embedding job started. |
| `MemoryEmbeddingCompleted` | Embedding job finished successfully. |
| `MemoryEmbeddingFailed` | Embedding job failed. |
| `MemoryEmbedded` | A memory item was stored with an embedding. |
| `MemoryUpdated` | Memory store was updated (non-embedding or general). |
| `PolicyEvaluated` | Governance policy was evaluated (allow/deny path). |
| `PolicyDenied` | Policy denied the action. |
| `PolicyViolated` | A policy breach was recorded. |
| `EscalationTriggered` | Escalation rules fired. |
| `ManualInterventionRequested` | Human-in-the-loop or manual step requested. |
| `AuthFailed` | Authentication failed for the request or step. |
| `LimitExceeded` | A runtime limit was exceeded (tokens, rate, concurrency, etc.). |
| `BillingPolicyViolated` | Billing or quota policy blocked execution. |
| `ValidationFailed` | Input or schema validation failed. |
| `SecretAccessed` | Auditable access to a secret (sensitive operation). |
| `NodePromptUpdated` | A node-level prompt was updated during the run (e.g. HITL edit). |
| `NodePromptExecuted` | A node prompt was executed after update. |

**Payload honesty:** `payload` is intentionally flexible. For exact keys per path, follow the emitter (e.g. `src/domain/execution/services/observability/hooks.py`, graph runtime, LLM services). This reference guarantees **stable `type` strings** for filtering and analytics, not a single JSON schema for all events.

---

## Authoring events

### Row shape (`authoring_event`)

| Column | Description | Type (SQL) |
|--------|-------------|------------|
| `event_type` | One of `AuthoringEventType` values below | `varchar(64)` |
| `resource_type` | Domain resource category (see `ResourceType` in `authoring_events.py`) | `varchar(64)` |
| `resource_id` | Identifier of the affected resource | `uuid` |
| `version_id` | Optional version identifier when the change targets a versioned entity | `uuid` or null |
| `change_type` | `CREATE`, `UPDATE`, or `DELETE` (`ChangeType`) | `varchar(64)` |
| `principal_id` | Actor (user or service principal) | `varchar(128)` |
| `justification` | Required audit justification string | `varchar(512)` |
| `occurred_at` | When the change was recorded | `timestamptz` |
| `schema_version` | Record schema evolution | `integer` |

See [Authoring event](../Glossary/terms/authoring-event.md) and [Governance policy versioning](../Glossary/terms/governance-policy-versioning.md).

### `AuthoringEventType` values

| Event name | Description |
|------------|-------------|
| `AGENT_CREATED` | A new agent record was created. |
| `AGENT_VERSION_CREATED` | A new agent version was created. |
| `NODE_AGENT_BINDING_CREATED` | A node-to-agent binding was created. |
| `TOOL_IMPORTED` | A tool was imported into the registry. |
| `TOOL_CONFIG_CREATED` | A tool configuration was created. |
| `TOOL_CONFIG_PUBLISHED` | A tool configuration was published. |
| `TOOL_CONFIG_DEPRECATED` | A tool configuration was deprecated. |
| `TOOL_CONFIG_DISABLED` | A tool configuration was disabled. |
| `AGENT_VERSION_TOOL_BINDING_CREATED` | A binding between an agent version and a tool was created. |
| `VERSION_PUBLISHED` | A flow (or versioned artefact) version was published. |
| `VERSION_ACTIVATED` | A version was activated for use. |
| `VERSION_ROLLED_BACK` | Activation was rolled back to a prior version. |
| `RAG_CONFIG_CREATED` | RAG configuration was created. |
| `RAG_CONFIG_VALIDATED` | RAG configuration passed validation. |
| `RAG_CONFIG_PUBLISHED` | RAG configuration was published. |
| `RAG_CONFIG_DEPRECATED` | RAG configuration was deprecated. |
| `RAG_CONFIG_DISABLED` | RAG configuration was disabled. |
| `RAG_CHUNKING_RULE_CREATED` | A chunking rule was created. |
| `RAG_CHUNKING_RULE_UPDATED` | A chunking rule was updated. |
| `TENANT_TOKEN_ISSUED` | A tenant-scoped token was issued (audit). |

---

## Conversation SSE events

These are **streamed** to clients as `ConversationEvent` with `event_type` + `payload` (see `src/domain/conversation/schemas/conversation.py`). They are **not** a 1:1 mirror of `ExecutionEventType` strings.

| Event name | Description |
|------------|-------------|
| `connected` | Stream established. |
| `flow_started` | Conversation associated flow execution started from the client’s perspective. |
| `node_started` | A graph node started (streaming progress). |
| `node_completed` | A graph node completed. |
| `edge_evaluated` | An edge was evaluated (streaming progress). |
| `flow_completed` | Flow finished successfully in this session. |
| `flow_failed` | Flow failed in this session. |
| `done` | Stream is complete; no further events for this request. |
| `error` | An error was surfaced on the stream. |
| `ping` | Keep-alive / heartbeat. |
| `content_delta` | Incremental assistant content (token or chunk delta). |

---

## Callbacks vs persisted events (summary)

| Mechanism | Typical use | Delivery |
|-----------|-------------|----------|
| SSE (`SSEEventType`) | Live UX: typing indicators, progressive output, client-side routing | Browser/EventSource or HTTP client |
| Execution events (`ExecutionEventType`) | Durable audit, analytics, replay, operator dashboards | Postgres `execution_event` |
| Authoring events (`AuthoringEventType`) | Compliance and design-time audit | Postgres `authoring_event` |

For **business logic that must not be lost** when a user disconnects, rely on **persisted** execution or authoring data (and idempotent APIs), not only on the live SSE stream.

## Related

- [Flow lifecycle](../Execution/flow-lifecycle.md)
- [Runtime vs authoring](../Architecture/runtime-vs-authoring.md)
- [Tracing and cost](tracing-and-cost.md)
- [Documentation map (AI)](../AI/documentation-map.md)
