# Payments example

A market-standard payments API, imported into `agent-orchestration-core` from its own
`openapi.json`, reviewed, partly approved, and then driven from conversation.

This is the end-to-end path: **run an upstream API → import its operations as tools → approve a
subset → provision the whole tenant → talk to it.**

## The upstream API

[`examples/api/payments_api.py`](../api/payments_api.py) is a real FastAPI application. It runs
in-process on an ephemeral port and serves its own generated `openapi.json`, which the
orchestrator fetches server-side during import.

| operation_id | method | path | what it does |
|---|---|---|---|
| `payments_create_payment` | POST | `/v1/payments` | charge a customer |
| `payments_capture_payment` | POST | `/v1/payments/capture` | capture an authorization |
| `payments_create_refund` | POST | `/v1/refunds` | refund a captured payment |
| `payments_list_payments` | GET | `/v1/payments` | list and filter payments |
| `payments_get_payment` | GET | `/v1/payments/lookup` | read one payment |
| `payments_create_payout` | POST | `/v1/payouts` | send settled funds to a bank account |
| `payments_get_balance` | GET | `/v1/balance` | available and pending balance |

It behaves the way a payments provider does: amounts are integers in minor units, an
`Idempotency-Key` replays the original payment instead of charging twice, and a card charge of
1000.00 or more comes back `201` with `status: declined` rather than as an HTTP error.

It can also be told to fail on purpose — `fail_next_calls(n, mode)` with `hangup` (drops the
connection mid-response), `timeout`, or `status_502`.

## Running it

Prerequisites are the same as the other API examples:

```bash
docker compose up -d postgres redis
make migrate
PYTHONPATH=src uv run uvicorn src.app:app --port 8000
```

`.env` needs `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE` and a working `OPENAI_API_KEY` — the flow
makes real LLM calls for moderation, tool selection, slot filling and response rendering.

```bash
PYTHONPATH=src uv run python -m examples.payments.setup

PYTHONPATH=src uv run python -m examples.payments.charge_and_refund
PYTHONPATH=src uv run python -m examples.payments.read_only_queries
PYTHONPATH=src uv run python -m examples.payments.withheld_operation
PYTHONPATH=src uv run python -m examples.payments.declined_charge
PYTHONPATH=src uv run python -m examples.payments.upstream_failure_and_sla
```

`setup.py` provisions a fresh tenant on every run and writes its ids to
`examples/.state/payments_tenant_setup.json`, which the scenarios read. It is safe to repeat.

## Scenarios

| Scenario | Demonstrates |
|---|---|
| `charge_and_refund` | Two turns. `49.90 US dollars` becomes `amount_minor: 4990`; the second turn refunds part of the payment created by the first, using an id the slot filler has never seen in any schema example. |
| `read_only_queries` | GET tools. The balance question and a customer-history question resolve read-only operations, and the filled slots travel as query parameters instead of a JSON body. Asserts no write call happened. |
| `withheld_operation` | The approval gate at runtime. A payout request retrieves the withheld operation's catalog document, that hit is dropped because its config is not `PUBLISHED`, and the assistant answers from the tenant's payout policy instead. Asserts nothing wrote. |
| `declined_charge` | A decline is not a failure. The HTTP call succeeds, so `ToolErrorHandlerNode` never runs and nothing is retried — reading the refusal out of the response body is `ResponseBuilder`'s job. |
| `upstream_failure_and_sla` | A genuinely unreachable API: one bounded retry, then escalation, with the SLA case carrying `fallback_reason: TOOL_FAILURE`. |

## The approval gate

`POST /core/v1/tools/import-tools` takes `openapi_url`, fetches the document server-side and
creates one `tool` plus one `tool_config` per operation. It **already publishes** every config it
creates, so `:publish` afterwards is an idempotent no-op that records the approval as an authoring
event.

The half that changes state is the other one. `setup.py` approves five operations and calls
`:disable` on `payments_capture_payment` and `payments_create_payout` — capture belongs to the
fulfilment team, and payouts move money out of the business and need dual approval in finance.
`ToolCatalogRetriever` hydrates `PUBLISHED` configs only, so a disabled operation can be retrieved
but never selected.

Provisioning indexes catalog documents for the withheld operations too, on purpose. Skipping them
would make the gate look effective when nothing had actually tested it.

## Things this example encodes

**Path parameters do not work.** Neither `effective_tool_http_url` nor `HttpToolExecutor`
interpolates `{placeholder}`, and the OpenAPI parser merges path parameters into the request schema
as ordinary properties. An imported operation whose path is templated would be called with the
literal `{id}` in the URL. That is why every operation here takes its identifiers in the body or
the query string — `/v1/payments/lookup?payment_id=…`, not `/v1/payments/{payment_id}`.

**`operationId` becomes a globally unique tool name.** `Tool.name` is unique across all tenants and
`get_tool_by_name` is not tenant-scoped, so the operation ids are prefixed. Without an explicit
`operationId`, FastAPI generates names like `create_payment_v1_payments_post`, and the parser's own
fallback is worse — `post_/v1/payments`.

**Re-importing into the same tenant creates a second published config.** Versions go `1.0.0`,
`1.0.1`, … and the old ones are not deprecated, so `ToolExecutor` can report
`ready_operation_tool_config_ambiguous`. The setup script resolves the newest config per tool.

**Retrieval threshold.** `ToolCatalogRetriever` applies `min(config threshold, 0.42)`. Correct
matches score between 0.32 and 0.58 with `text-embedding-3-large`: `"refund 15.00 of payment X"`
scores 0.53 against the refund aliases, but `"how much money do we have"` scores only 0.32 against
the balance aliases. At the 0.5 that reads like a safe default, the loose half of the intent space
retrieves nothing and `ToolResolver` returns `[]` without ever calling the LLM. This example uses
0.25.

**The embedding pair.** Documents are embedded with `indexing_embedding`
(`text-embedding-3-large`, 3072) and queries with the *same* model truncated to
`embedding.dimension` (1536). Pointing `embedding` at a different model family would compare
incompatible vector spaces and score every pair near 0.05 — ranking noise that still looks like
retrieval.

**`ToolCatalogIndexer` is not wired.** `containers.py` builds `ToolsService` without it, so the
parameter defaults to `None` and the automatic per-operation catalog write on import never
happens. Every catalog document this tenant retrieves on is one the example ingests itself.

**Imported tools require interaction metadata.** Import binds the upstream `Authorization` header
to `interaction_metadata_key: end_user_authorization`. A flow run without that key in
`metadata` fails every tool call with `interaction_metadata_header_missing`.

**An upstream 5xx counts as a successful tool run.** `HttpToolExecutor` never calls
`raise_for_status`, so only transport-level failures reach the retry and fallback path — which is
why `upstream_failure_and_sla` makes the stub hang up rather than return 502. See
[Known limitations](../../docs/Develop/limitations.md).

## Layout

```
examples/payments/
├── setup.py                      provision the tenant, import and approve the tools
├── knowledge.py                  English tenant knowledge and tool alias clusters
├── _common.py                    scenario helpers bound to the payments state file
├── charge_and_refund.py
├── read_only_queries.py
├── withheld_operation.py
├── declined_charge.py
└── upstream_failure_and_sla.py
```

The domain-agnostic provisioning stages live in
[`examples/api/provisioning.py`](../api/provisioning.py) and are shared with
[`examples/full_tenant_setup.py`](../full_tenant_setup.py).
