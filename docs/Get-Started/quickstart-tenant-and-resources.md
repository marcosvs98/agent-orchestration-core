# Quickstart: configure a tenant and use the three execution surfaces

A step-by-step guide from an empty tenant to a working execution, using nothing but `curl`.

Every command below was run against a live service (Postgres, Redis and a real LLM provider) and
the outputs are the real ones. Where something does **not** work on the current build, it says so
rather than showing a command that fails.

**Who this is for:** an operator or an agent (human or automated) provisioning a tenant for the
first time. It assumes no prior knowledge of the domain model.

**Related:** [Full tenant configuration](full-tenant-configuration.md) is the exhaustive
reference; this page is the short path. [Agent runtime](../Execution/agent-runtime.md) documents
the agent-run surface in depth.

---

## The three surfaces

AOC exposes three ways to make an agent do work. They share the same tenant, agents, tools and
governance; they differ in who drives the loop.

| Surface | Endpoint | Use it when | Response |
|---------|----------|-------------|----------|
| **Agent run** (incl. A2A) | `POST /core/v1/executions/agent-runs` | A task with a defined start and end: "do this, tell me the result". The runtime owns the tool loop. | JSON, one object per run |
| **Conversation** | `POST /core/v1/conversations` | An interactive turn where a person is waiting and you want tokens as they are produced. | SSE stream |
| **Flow run** (graph) | `POST /core/v1/executions/flow-runs` | A fixed, auditable path over a versioned node graph, where the *shape* of the work is the product. | JSON, one object per run |

Rule of thumb: **agent run** = give the agent a goal and let it decide the steps;
**flow run** = you decide the steps and the agent fills them in; **conversation** = the same as an
agent run but streamed to a user interface.

---

## Conventions

```bash
export API=http://127.0.0.1:8000
```

Two shell notes that will save you time:

- In **zsh**, write `"${VAR}:activate"`, never `"$VAR:activate"`. Bare `$VAR:a` is a zsh
  parameter modifier and silently rewrites the URL, producing a confusing `404`.
- Send request bodies on **one line**. A multi-line `-d '...'` string in zsh can inject control
  characters that the JSON parser rejects.

Every write endpoint is `Content-Type: application/json`. Execution endpoints additionally
require an `Idempotency-Key` header.

---

## Step 0 — Check the service

```bash
curl -s $API/health
```

```json
{"status":"healthy","components":{"database":{"status":"ok"},"redis":{"status":"ok"}}}
```

If `status` is `degraded`, fix the dependency before continuing — nothing below will work.

---

## Step 1 — Tenant and credentials

A tenant is the isolation boundary. Every object you create below belongs to exactly one tenant,
and `tenant_id` is always taken from the token, never from a request body.

Creating the first tenant needs a platform credential. In development:

```bash
PYTHONPATH=src uv run python resources/generate_jwt_token.py
```

Create the tenant:

```bash
curl -s -X POST "$API/core/v1/tenants" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Acme Support","description":"demo tenant","timezone":"UTC","currency":"USD"}'
```

```json
{"id":"8748be2f-803f-4eba-8ea5-9157071910cc","name":"Acme Support","is_active":true}
```

Then obtain a token **scoped to that tenant**. In development, re-run the generator with
`ADMIN_TENANT_ID` set to the new id:

```bash
export TENANT_ID=8748be2f-803f-4eba-8ea5-9157071910cc
export TOKEN=$(ADMIN_TENANT_ID=$TENANT_ID PYTHONPATH=src \
  uv run python resources/generate_jwt_token.py | grep '^ey')
```

Verify:

```bash
curl -s "$API/core/v1/tenants/current" -H "Authorization: Bearer $TOKEN"
```

> **Note.** `POST /core/v1/auth/tenant-token` exchanges a platform credential for a tenant token,
> but it refuses when the caller's token is already bound to a *different* tenant
> (`tenant_scope_mismatch`). For bootstrapping a brand-new tenant, mint the token directly as
> above.

---

## Step 2 — Model and AI execution policy

An **AI execution policy** says which model an agent version runs on. Agents point at a
*published version* of a policy, so changing a model is a versioned, auditable act.

Models are a **global catalogue**, not per tenant. Reuse an existing entry:

```bash
curl -s "$API/core/v1/models" -H "Authorization: Bearer $TOKEN"
```

```json
[{"id":"00000000-0000-0000-0000-000000000300","name":"gpt-4o-mini"}, ...]
```

> **Gotcha.** `model.name` is globally unique. `POST /core/v1/models` with a name another tenant
> already registered fails with a `500`. Reuse the catalogue entry instead — the `name` is the
> provider's model id, so it must match a real model anyway.

```bash
export MODEL_ID=00000000-0000-0000-0000-000000000300

POLICY_ID=$(curl -s -X POST "$API/core/v1/ai-execution-policies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"description":"Acme default LLM policy"}' | jq -r .id)

PV_ID=$(curl -s -X POST "$API/core/v1/ai-execution-policy-versions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"ai_execution_policy_id\":\"$POLICY_ID\",\"model_id\":\"$MODEL_ID\"}" | jq -r .id)
```

Versions move `DRAFT → VALIDATED → PUBLISHED`. Only published versions may be used:

```bash
curl -s -X POST "$API/core/v1/ai-execution-policies/$POLICY_ID/versions/${PV_ID}:validate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'

curl -s -X POST "$API/core/v1/ai-execution-policies/$POLICY_ID/versions/${PV_ID}:publish" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"change_type":"CREATE","justification":"initial publish"}'
```

```json
{"id":"64f91aa3-…","status":"PUBLISHED","model_id":"00000000-…-000000000300"}
```

---

## Step 3 — Billing policy

The runtime refuses to start an agent run without an **active** billing policy version — spend
must be attributable before it is incurred.

```bash
BP_ID=$(curl -s -X POST "$API/core/v1/billing-policies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"acme-billing"}' | jq -r .id)

BPV_ID=$(curl -s -X POST "$API/core/v1/billing-policies/$BP_ID/versions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"payload":{"currency":"USD"}}' | jq -r .id)

curl -s -X POST "$API/core/v1/billing-policies/versions/${BPV_ID}:publish" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"change_type":"CREATE","justification":"initial"}'

curl -s -X POST "$API/core/v1/billing-policies/versions/${BPV_ID}:activate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"change_type":"CREATE","justification":"initial"}'
```

Skipping this gives `409 billing_policy_not_active` at run time, not at configuration time.

---

## Step 4 — Governance (access + rate limits)

Every execution endpoint passes two gates before any work happens: a **rate-limit policy** and an
**access policy**. Both must exist and be published for the *action* you are calling, or the call
is denied — a tenant with no policy is denied, not allowed.

```bash
RLP_ID=$(curl -s -X POST "$API/core/v1/rate-limit-policies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"acme-rate-limits"}' | jq -r .id)
```

One version per action. **Versions are unique per policy**, so bump `version_patch` each time:

```bash
P=0
for ACTION in execution:agent_run:create execution:agent_run:get \
              execution:agent_runs:list execution:agent_run:cancel \
              conversation:turn:create execution:flow_run:create; do
  V=$(curl -s -X POST "$API/core/v1/rate-limit-policies/$RLP_ID/versions" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"action\":\"$ACTION\",\"principal_type\":\"human\",\"limit\":1000,\"window_seconds\":60,\"version_major\":1,\"version_minor\":0,\"version_patch\":$P}" | jq -r .id)
  curl -s -o /dev/null -X POST "$API/core/v1/rate-limit-policies/versions/${V}:publish" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"change_type":"CREATE","justification":"initial"}'
  P=$((P+1))
done
```

The access policy is a single allow-list:

```bash
AP_ID=$(curl -s -X POST "$API/core/v1/access-policies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"acme-access"}' | jq -r .id)

APV_ID=$(curl -s -X POST "$API/core/v1/access-policies/$AP_ID/versions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"rules":{"allow":["execution:agent_run:create","execution:agent_run:get","execution:agent_runs:list","execution:agent_run:cancel","conversation:turn:create","execution:flow_run:create"]}}' | jq -r .id)

curl -s -X POST "$API/core/v1/access-policies/versions/${APV_ID}:publish" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"change_type":"CREATE","justification":"initial"}'
```

**Reading the denials.** They are precise, so use them:

| Message | Meaning |
|---------|---------|
| `rate_limit_policy_not_configured` | No rate-limit policy for this tenant |
| `rate_limit_policy_not_published` | No published version for **this action** |
| `access_policy_not_configured` | No access policy for this tenant |
| `action_not_allowed` | The action is missing from the allow-list |

To widen the allow-list later, publish a **new version** with a higher `version_*` — do not edit
the published one.

---

## Step 5 — Tools

Tools are imported from an OpenAPI document; there is no endpoint that creates one by hand. Each
operation becomes a `tool` plus a **published** `tool_config` holding the URL, method, headers and
request schema.

```bash
curl -s -X POST "$API/core/v1/tools/import-tools" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"openapi_url":"https://your.api/openapi.json","name":"acme-api"}'
```

```json
{"imported_count":170,"tools":[{"name":"health_check_health_get"}, ...]}
```

The tool **name** is what the model sees and what you use in a run's tool grant.

### Authenticated tools

The importer binds an `Authorization` header to a run-scoped value:

```json
"headers": {"Authorization": {"interaction_metadata_key": "end_user_authorization"}}
```

Supply it per execution in `metadata` (see Step 7). Alternatively create a config with a fixed
header:

```bash
curl -s -X POST "$API/core/v1/tool-configs" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"tool_id\":\"$TOOL_ID\",\"config\":{\"base_url\":\"https://your.api\",\"path\":\"/things\",\"method\":\"GET\",\"operation_id\":\"listThings\",\"description\":\"Lists things\",\"headers\":{\"Authorization\":\"Bearer …\"},\"request_schema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}}}"

curl -s -X POST "$API/core/v1/tool-configs/${TOOL_CONFIG_ID}:publish" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
```

A tool config must be `PUBLISHED` to be usable.

---

## Step 6 — Agents

An **agent** is persistent configuration. An **agent version** is an immutable snapshot of it:
system prompt, persona, AI execution policy, tool bindings.

```bash
AGENT_ID=$(curl -s -X POST "$API/core/v1/agents" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"ops-reporter"}' | jq -r .id)

AGENT_V=$(curl -s -X POST "$API/core/v1/agents/$AGENT_ID/versions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"description\":\"Reports on platform status\",\"system_prompt\":\"You are the Ops Reporter. Answer operational questions using the tools you were granted. Be factual and concise.\",\"persona_config\":{\"language\":\"en_US\",\"tone\":\"professional\",\"style\":\"concise\",\"rules\":[\"Never invent numbers; use tool results only.\"],\"max_response_length\":600},\"ai_execution_policy_version_id\":\"$PV_ID\"}" | jq -r .id)
```

`ai_execution_policy_version_id` is what makes the version executable. Omit it and every run
fails with `ai_execution_policy_not_active`. A policy version belonging to another tenant is
rejected with `404 ai_execution_policy_version_not_found`.

Bind the tools this agent may ever use:

```bash
curl -s -X POST "$API/core/v1/agent-version-tool-bindings" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"agent_version_id\":\"$AGENT_V\",\"tool_config_id\":\"$TOOL_CONFIG_ID\"}"
```

Then promote the version. Only an **active, published** version is executable:

```bash
for STEP in validate publish activate; do
  curl -s -X POST "$API/core/v1/agents/$AGENT_ID/versions/${AGENT_V}:${STEP}" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"change_type":"CREATE","justification":"initial"}'
done
```

Confirm the whole tenant in one call:

```bash
curl -s "$API/core/v1/tenants/current/summary" -H "Authorization: Bearer $TOKEN"
```

---

## Step 7 — Surface 1: Agent runs

The agent is given a goal; the runtime runs the loop
`LLM → tool call → tool result → LLM → … → final output` until the agent answers or the iteration
budget runs out.

```bash
curl -s -X POST "$API/core/v1/executions/agent-runs?wait=true" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: run-001' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"instruction\":\"Is the platform healthy? Report the status and which components are up.\",\"context\":[{\"key\":\"incident\",\"content\":\"Incident INC-4471 is open; the on-call engineer needs a one-line status.\",\"description\":\"Open incident\"}],\"tools\":{\"allowed_tool_names\":[\"health_check_health_get\"]},\"metadata\":{\"end_user_authorization\":\"Bearer $TOKEN\"},\"max_iterations\":4}"
```

```json
{
  "id": "d3caf10d-f9c0-4648-ad9c-96bed033412f",
  "origin": "DIRECT",
  "canonical_status": "COMPLETED",
  "finish_reason": "FINAL_OUTPUT",
  "iterations_used": 2,
  "model": "gpt-4o-mini",
  "input_tokens": 702, "output_tokens": 67,
  "output": {"text": "The platform is currently healthy. Database: OK, 1.95 ms. Redis: OK, 0.33 ms."}
}
```

### The four fields that matter

| Field | What it does |
|-------|--------------|
| `instruction` | The task. Required. |
| `context` | Execution-scoped context: `{key, content, description}`. Recorded on the run and injected as *caller-supplied* data — never merged into the agent's configuration. Use it for the ticket, the account, the incident. |
| `tools.allowed_tool_names` | The subset of the agent's bound tools this run may use. Omit for all; `[]` for none. |
| `metadata` | Run-scoped string values. Tool configs bind headers to these (`interaction_metadata_key`). |

`max_iterations` bounds the loop (default 8, ceiling 25).

### Tool authorization is enforced, not advised

Withhold the tool and the model is never offered it, no `tool_run` row is created, and it says so:

```bash
curl -s -X POST "$API/core/v1/executions/agent-runs?wait=true" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: run-002' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"instruction\":\"Check platform health with your tool.\",\"tools\":{\"allowed_tool_names\":[]}}"
```

```json
{"canonical_status":"COMPLETED","output":{"text":"I currently do not have access to a tool that can check the platform's health status."}}
```

Asking for a tool the agent version is not bound to is refused before the run starts:

```json
{"code":"DOMAIN_VALIDATION","message":"tool_not_bound_to_agent_version"}
```

### Inspecting a run

```bash
curl -s "$API/core/v1/executions/agent-runs/$RUN_ID" -H "Authorization: Bearer $TOKEN"
```

Returns the frozen `tool_grant`, the `context_snapshot`, the full `messages` transcript (each
labelled with `source` and `trust_level`), `events`, `tool_calls`, `artifacts` and `delegations`.
Typical event sequence:

```
AgentRunStarted → LLMCallStarted → LLMCallCompleted → ToolInvocationRequested
→ ToolInvocationSucceeded → LLMCallStarted → LLMCallCompleted → AgentRunCompleted
```

### Asynchronous runs

`?wait=false` returns `202` immediately and executes in the background; poll the detail endpoint.

```bash
curl -s -X POST "$API/core/v1/executions/agent-runs?wait=false" ... # → 202, status CREATED
curl -s "$API/core/v1/executions/agent-runs/$RUN_ID" ...            # → RUNNING → COMPLETED
curl -s -X POST "$API/core/v1/executions/agent-runs/${RUN_ID}:cancel" ...  # → CANCELLED
```

Cancelling a terminal run returns `409`. Replaying the same `Idempotency-Key` returns the same
run; omitting the header is a `400`.

### Listing

```bash
curl -s "$API/core/v1/executions/agent-runs?agent_id=$AGENT_ID&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

Filters: `agent_id`, `flow_run_id`, `root_agent_run_id`, `parent_agent_run_id`.

---

## Step 8 — Surface 1b: A2A (agent-to-agent)

When a task needs a capability the agent does not have, it delegates to another agent using the
[Agent2Agent protocol](https://a2a-protocol.org/). The delegated work is a **task with its own
run**, not a function call.

Grant delegation explicitly, naming the agents that may be reached:

```bash
curl -s -X POST "$API/core/v1/executions/agent-runs?wait=true" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'Idempotency-Key: run-a2a-1' \
  -d "{\"agent_id\":\"$AGENT_A\",\"instruction\":\"Produce a two-line ops brief: (1) is the platform healthy, and (2) how many agents does this tenant have configured? You do not have a tool for the second question - delegate it.\",\"tools\":{\"allowed_tool_names\":[\"health_check_health_get\"],\"allow_agent_delegation\":true,\"delegate_agent_ids\":[\"$AGENT_B\"]},\"metadata\":{\"end_user_authorization\":\"Bearer $TOKEN\"},\"max_iterations\":6}"
```

```json
{"canonical_status":"COMPLETED","finish_reason":"FINAL_OUTPUT","iterations_used":2,
 "output":{"text":"The platform is healthy, with all components operational. There are 2 agents configured for this tenant."}}
```

Agent A's events show the tool call *and* the delegation:

```
AgentRunStarted → LLMCallStarted → LLMCallCompleted → ToolInvocationRequested
→ ToolInvocationSucceeded → ToolInvocationRequested → AgentDelegationCompleted
→ LLMCallStarted → LLMCallCompleted → AgentRunCompleted
```

and its `delegations` array records the A2A task:

```json
{"a2a_task_id":"644f38e1d848…","a2a_context_id":"18e18116e8ef…","a2a_task_state":"completed",
 "transport":"internal","target_agent_id":"08ea3071-…","child_agent_run_id":"3ace9e1c-…"}
```

Agent B's run is a first-class run of its own:

```json
{"id":"3ace9e1c-…","origin":"A2A_DELEGATION","delegation_depth":1,
 "parent_agent_run_id":"18e18116-…","root_agent_run_id":"18e18116-…",
 "canonical_status":"COMPLETED","tool_calls":[["get_current_summary…","SUCCESS",200]]}
```

Retrieve the whole tree by root:

```bash
curl -s "$API/core/v1/executions/agent-runs?root_agent_run_id=$RUN_A" -H "Authorization: Bearer $TOKEN"
```

Delegation depth is bounded, and agent B may not delegate onward unless its own run grants it.

### Serving A2A to external agents

Publish an agent's capabilities as an **Agent Card**:

```bash
curl -s "$API/core/v1/agents/$AGENT_ID/agent-card" -H "Authorization: Bearer $TOKEN"
```

```json
{"protocolVersion":"0.3.0","name":"tenant-analyst","version":"1.0.1",
 "capabilities":{"streaming":false,"pushNotifications":false,"stateTransitionHistory":true},
 "defaultInputModes":["text/plain","application/json"],
 "skills":[{"id":"getTenantSummary","name":"…","description":"Tenant configuration summary","tags":["tool"]}]}
```

Skills are derived from the tools the **active** version is bound to, so the card never drifts
from the published configuration.

Then submit tasks over JSON-RPC 2.0:

```bash
curl -s -X POST "$API/core/v1/agents/$AGENT_ID/a2a" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"req-1","method":"message/send","params":{"message":{"kind":"message","messageId":"msg-1","role":"user","parts":[{"kind":"text","text":"How many tools does this tenant have configured?"}]}}}'
```

```json
{"jsonrpc":"2.0","id":"req-1","result":{"kind":"task","id":"0ada4136-…","contextId":"0ada4136-…",
 "status":{"state":"completed","message":{"role":"agent","parts":[{"kind":"text","text":"66"}]}},
 "artifacts":[{"artifactId":"final-output-1","name":"final-output"}]}}
```

Supported methods and their errors:

| Method | Notes |
|--------|-------|
| `message/send` | Creates an agent run and returns the terminal `Task`. The task id **is** the agent run id. |
| `tasks/get` | `{"id": "<task id>"}` |
| `tasks/cancel` | Cancels the underlying run |

| Situation | JSON-RPC error |
|-----------|----------------|
| Unsupported method (e.g. `message/stream`) | `-32601 method_not_found` |
| Message with no text part | `-32602 invalid_params` |
| Unknown task | `-32001 agent_run_not_found` |

---

## Step 9 — Surface 2: Conversation over SSE

Same agents and tools, but the turn is streamed as `text/event-stream` for a user interface.

```bash
curl -N -X POST "$API/core/v1/conversations" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' -H 'Idempotency-Key: conv-001' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"user_id\":\"e2e-operator\",\"user_input\":\"In one sentence, what does an ops reporter do?\"}"
```

```
event: connected
data: {"session_id": "8ab17df2-…", "correlation_id": "ba911f53-…", "interaction_id": null}
id: 1

event: content_delta
data: {"delta": "An", "source_event_type": "response.output_text.delta"}
id: 2

event: content_delta
data: {"delta": " ops", "source_event_type": "response.output_text.delta"}
id: 3

…

event: done
data: {"session_id": "3a00e427-…", "correlation_id": "a788fe79-…", "final_text": "ACK"}
```

| Event | Meaning |
|-------|---------|
| `connected` | Stream open; carries `session_id` and `correlation_id` |
| `content_delta` | One token chunk in `delta` |
| `tool_progress` | A provider-side tool call started or completed |
| `done` | Terminal; `final_text` is the complete answer |
| `error` | Terminal; carries `error_code`, `correlation_id`, `trace_id` |

### Rules worth knowing before you integrate

- **`user_id` must equal the token's `principal_id`** for a `human` principal, otherwise the
  stream fails with `user_id_principal_mismatch`. Machine principals may act for any end user.
- `Idempotency-Key` is required, exactly as for agent runs. Missing it returns
  `400 missing_idempotency_key` **before** the stream opens.
- **Errors arrive inside the stream, with HTTP 200.** Do not treat the status line as success;
  read events until `done` or `error`.

### Multi-turn

Pass prior turns in `metadata.message_history` (max 50 items, roles `user`/`assistant`):

```bash
curl -N -X POST "$API/core/v1/conversations" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' -H 'Idempotency-Key: conv-002' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"user_id\":\"e2e-operator\",\"user_input\":\"What is my favourite colour?\",\"metadata\":{\"message_history\":[{\"role\":\"user\",\"content\":\"My favourite colour is teal.\"},{\"role\":\"assistant\",\"content\":\"Noted, teal.\"}]}}"
```

```
event: done
data: {"final_text": "Your favourite colour is teal."}
```

Some metadata keys are reserved and rejected — `tenant_id`, `user_id`,
`end_user_authorization` (and its legacy alias), `headers`, `current_date`, `mcp_server_url`:

```
event: error
data: {"error_code": "forbidden_metadata_key:tenant_id", "correlation_id": "…", "trace_id": "…"}
```

> Reusing a `session_id` across turns groups them for correlation. It did **not** carry
> conversational memory on the build this guide was validated against — pass
> `metadata.message_history` when you need the model to see prior turns.

---

## Step 10 — Surface 3: Flow runs (graph)

A **flow** is a versioned graph of typed nodes. Use it when the sequence of steps is the product
and must be identical every time: moderation, then classification, then a tool, then a response.

The authoring sequence below is validated end to end; see the caveat at the end of this section
before relying on graph *execution*.

### 10.1 Node prompts

Each node type renders a prompt template with an output schema. Read the active one:

```bash
curl -s "$API/core/v1/nodes/ContentModeration/prompt" -H "Authorization: Bearer $TOKEN"
curl -s "$API/core/v1/nodes/ResponseBuilder/prompt"   -H "Authorization: Bearer $TOKEN"
```

or create your own:

```bash
curl -s -X POST "$API/core/v1/nodes/ResponseBuilder/prompt" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"node_type":"ResponseBuilder","template_text":"Answer the user in one short sentence.\n\n# User input\n{{ ctx.input.input_payload.user_input }}\n\nReturn JSON only.","output_schema":{"type":"object","additionalProperties":false,"properties":{"system_output":{"type":"string"},"turn_status":{"type":"string","enum":["completed","failed"]}},"required":["system_output","turn_status"]},"created_by":"operator"}'
```

> **Important.** `node_prompt` is a **global** table with no tenant column, and exactly one row
> per node type may be active. Creating a prompt for a node type **deactivates every other
> tenant's** prompt for that type. On a shared environment, read the active prompt and reuse its
> id rather than creating one. If `GET` returns a `500`, there is more than one active row for
> that type and the data needs repairing before the endpoint will work.

### 10.2 Flow, version, nodes

```bash
FLOW_ID=$(curl -s -X POST "$API/core/v1/flows" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"acme-support-flow","description":"moderation -> response"}' | jq -r .id)

FV_ID=$(curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' | jq -r .id)

N1=$(curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/$FV_ID/nodes:custom" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"flow_id\":\"$FLOW_ID\",\"flow_version_id\":\"$FV_ID\",\"node_type\":\"ContentModeration\",\"node_prompt_id\":\"$CM_PROMPT\",\"allow_session_context\":true}" | jq -r .id)

N2=$(curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/$FV_ID/nodes:custom" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"flow_id\":\"$FLOW_ID\",\"flow_version_id\":\"$FV_ID\",\"node_type\":\"ResponseBuilder\",\"node_prompt_id\":\"$RB_PROMPT\",\"allow_session_context\":true}" | jq -r .id)
```

Available node types: `GET /core/v1/flows/node-templates:system`.

### 10.3 Bind each node to an agent version and an AI policy

```bash
for N in $N1 $N2; do
  curl -s -X POST "$API/core/v1/node-agent-bindings" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"node_id\":\"$N\",\"agent_version_id\":\"$AGENT_V\"}"
  curl -s -X POST "$API/core/v1/node-ai-execution-policy-bindings" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"node_id\":\"$N\",\"ai_execution_policy_version_id\":\"$PV_ID\"}"
done
```

### 10.4 Draft, validate, publish, compile, activate

The graph names the nodes, the start node, and the conditional edges between them.

> **Each node's `config` must carry `llm.model_alias`.** Unlike an agent run — which takes the
> model from the agent version's AI execution policy — a graph node reads it from its own config,
> falling back to the runtime policy. Omit it and the run fails with `llm_model_alias_required`.

```bash
LLM='{"llm":{"provider":"OPENAI","model_alias":"gpt-4o-mini","temperature":0.0,"max_tokens":512}}'

curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/$FV_ID/graph:draft" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"flow_id\":\"$FLOW_ID\",\"flow_version_id\":\"$FV_ID\",\"principal_id\":\"operator\",\"definition\":{\"start_node\":\"$N1\",\"nodes\":{\"$N1\":{\"type\":\"ContentModeration\",\"config\":$LLM},\"$N2\":{\"type\":\"ResponseBuilder\",\"config\":$LLM}},\"edges\":[{\"from_node\":\"$N1\",\"to_node\":\"$N2\",\"condition\":\"flagged == false\",\"edge_kind\":\"NORMAL\"}]}}"
```

`graph:validate`, `graph:compile` and the version lifecycle calls all take the same
`{flow_id, flow_version_id, principal_id}` body. The order matters — **compile only works on a
published version**:

```bash
BODY="{\"flow_id\":\"$FLOW_ID\",\"flow_version_id\":\"$FV_ID\",\"principal_id\":\"operator\"}"

curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/$FV_ID/graph:validate" -d "$BODY" …
curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/${FV_ID}:validate" -d '{}' …
curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/${FV_ID}:publish" \
     -d '{"change_type":"CREATE","justification":"initial"}' …
curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/$FV_ID/graph:compile" -d "$BODY" …
curl -s -X POST "$API/core/v1/flows/$FLOW_ID/versions/${FV_ID}:activate" \
     -d '{"change_type":"CREATE","justification":"initial"}' …
```

Compiling turns the draft into an immutable **flow graph snapshot**; the run binds to the
snapshot, not the draft.

### 10.5 Runtime policy

A tenant-scoped **runtime policy** supplies execution limits (and other defaults) for graph runs:

```bash
RP_ID=$(curl -s -X POST "$API/core/v1/runtime-policies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"scope":"TENANT","version":"1","policy_definition":{"llm":{"temperature":0.0,"max_tokens":1024,"timeout_ms":30000,"stream_enabled":false},"limits":{"max_depth":20,"max_nodes":50,"max_total_duration_ms":60000}}}' | jq -r .id)

curl -s -X POST "$API/core/v1/runtime-policies/${RP_ID}:activate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"change_type":"CREATE","justification":"initial"}'
```

Note that `RuntimePolicyLlmSchema` has **no `model_alias` field** — that is why the alias belongs
in the node config (10.4).

### 10.6 Run the flow

```bash
curl -s -X POST "$API/core/v1/executions/flow-runs?wait=true" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: flow-001' \
  -d "{\"flow_id\":\"$FLOW_ID\",\"session_id\":\"$(uuidgen)\",\"user_id\":\"e2e-operator\",\"input\":{\"user_input\":\"Hello, can you confirm you are reachable?\"}}"
```

Inspect progress:

```bash
curl -s "$API/core/v1/executions/flow-runs/$FLOW_RUN_ID" -H "Authorization: Bearer $TOKEN"
curl -s "$API/core/v1/executions/flow-runs/$FLOW_RUN_ID/graph-state" -H "Authorization: Bearer $TOKEN"
curl -s "$API/core/v1/executions/node-runs?flow_run_id=$FLOW_RUN_ID" -H "Authorization: Bearer $TOKEN"
curl -s "$API/core/v1/executions/execution-events?flow_run_id=$FLOW_RUN_ID" -H "Authorization: Bearer $TOKEN"
```

Events for a healthy run read:

```
FlowStarted → NodeStarted → NodeCompleted → EdgeEvaluated → NodeStarted → … → FlowCompleted
```

> **Known issues on the build this guide was validated against.**
>
> 1. **Activation is cached.** After activating a new flow version, `flow_id`-based runs may keep
>    resolving the previous version until the `flow_active_version:<flow_id>` Redis key expires.
>    Symptom: `409 flow_version_not_active` when targeting the new version explicitly. Address the
>    version directly with `flow_version_id`, or clear that cache key.
> 2. **Graph execution did not complete.** A two-node graph reached `ContentModeration`
>    successfully (real LLM call, `{"flagged": false}`), the edge evaluated `true`, `ResponseBuilder`
>    started, and the run then failed with
>    `{"reason":"STRUCTURAL_ERROR","code":"TypeError","message":"argument of type 'NoneType' is not iterable"}`.
>    The failure is in the graph runtime, not in configuration, and it is unrelated to the agent-run
>    and conversation surfaces, which both work. Treat 10.1–10.5 as validated and 10.6 as pending.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401` | No or invalid bearer token | Check the token and `JWT_ISSUER` / `JWT_AUDIENCE` |
| `rate_limit_policy_not_configured` / `_not_published` | No rate-limit policy, or none for this action | Step 4 |
| `access_policy_not_configured` / `action_not_allowed` | Access policy missing or action not allowed | Step 4 |
| `billing_policy_not_active` | No active billing policy version | Step 3 |
| `agent_version_not_active` | Version not activated | `…:validate` → `:publish` → `:activate` |
| `ai_execution_policy_not_active` | Agent version has no policy bound | Set `ai_execution_policy_version_id` at version creation |
| `tool_not_bound_to_agent_version` | Run asked for a tool the version is not bound to | Bind it, or drop it from `allowed_tool_names` |
| `interaction_metadata_header_missing` | Tool header binds to a run-scoped value that was not supplied | Add the key to the run's `metadata` |
| `missing_idempotency_key` | Header omitted on an execution endpoint | Add `Idempotency-Key` |
| `user_id_principal_mismatch` | Conversation `user_id` ≠ token `principal_id` | Send the principal's own id, or use a machine principal |
| `llm_model_alias_required` | Graph node config has no `llm.model_alias` | Step 10.4 |
| Unexpected `404` on a `:action` URL | zsh expanded `$VAR:a` as a modifier | Use `"${VAR}:action"` |

---

## Where to go next

- [Agent runtime](../Execution/agent-runtime.md) — the agent-run surface in depth: grants,
  delegation, artifacts, events.
- [Full tenant configuration](full-tenant-configuration.md) — the complete provisioning
  reference, including RAG and MCP.
- [Governance HTTP API and scopes](../Governance/http-api-and-scopes.md) — every action name.
- [Flow lifecycle](../Execution/flow-lifecycle.md) and
  [graph runtime](../Execution/graph-runtime/index.md) — how a flow run executes.
