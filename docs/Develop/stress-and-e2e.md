# Stress testing and end-to-end runs

This page describes how to bring up the whole platform with one command, drive real traffic
through all four execution surfaces, and read the result in Grafana.

Everything here runs against the **demo tenant** seeded by `start.sh` on container boot.

---

## 1. One compose file

`docker-compose.yml` is the single source of truth. It brings up the application, the Temporal
worker, their datastores, and the full observability plane:

```bash
docker compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| `app` | 8000 | FastAPI application |
| `worker` | — | Temporal worker |
| `postgres` | 5432 | System of record (pgvector) |
| `redis` | 6379 | Cache, idempotency, rate-limit counters |
| `temporal` | 7233 / 8233 | Durable execution + Web UI |
| `otel-collector` | 4318 / 8888 / 8889 | OTLP ingest, redaction, spanmetrics |
| `tempo` | 3200 | Traces |
| `loki` | 3100 | Logs |
| `prometheus` | 9090 | Metrics |
| `grafana` | 3000 | Dashboards (`admin` / `admin`) |

Two services stay behind profiles and do **not** start by default:

```bash
docker compose --profile docs up -d docs           # MkDocs on :8001
docker compose --profile legacy-mock up -d mock-api
```

The image is built from `uv.lock` with `uv sync --frozen`, so the container runs exactly the
dependency set the lockfile pins. Changing `pyproject.toml` without re-running `uv lock` fails
the build instead of silently resolving something new.

---

## 2. Prepare the tenant

The demo seed predates the agent-run and A2A surfaces, so three governance gates block them:
no published rate-limit policy for those actions, an access-policy allow list that does not
name them, and an inactive billing policy. One script fixes all three:

```bash
PYTHONPATH=src uv run python resources/scripts/stress/prepare_stress_env.py --revoke-mcp
```

What it does, all idempotent:

- publishes rate-limit policy versions for every action the driver exercises
  (default `100000` per `60s` **per principal**, high enough not to shape the test);
- publishes a **new** access-policy version whose allow list is the union of the current one
  and the actions the driver needs — published versions are immutable, so it never edits the
  existing one;
- activates the tenant's published billing policy version;
- `--revoke-mcp` parks the tenant MCP credential.

### Why `--revoke-mcp`

The demo tenant has an MCP credential pointing at the bundled demo API
(`DEMO_API_HTTP_BASE`, default `http://demo-api:8088` under Compose). When that service is not
running, the model provider fails to fetch the MCP tool list and **every conversation turn dies**
with `llm_provider_error`. Revoking the credential removes the dependency. Undo it with:

```bash
PYTHONPATH=src uv run python resources/scripts/stress/prepare_stress_env.py --restore-mcp
```

**Re-apply it after every app restart.** `start.sh` runs the demo seed on boot, and
`seed_27_tenant_mcp_credential.py` re-creates the credential — so `docker compose up -d app`
silently undoes the revocation and conversation turns start failing again.

Rate-limit counters live in Redis under `rate:{tenant}:{principal_type}:{principal}:{action}`.
After changing a policy, clear them so the new limit takes effect immediately:

```bash
docker compose exec redis redis-cli -n 3 flushdb
```

---

## 3. Drive load

```bash
PYTHONPATH=src uv run python resources/scripts/stress/stress_driver.py --duration 10m
```

The driver runs five planes concurrently, each with its own worker pool, HTTP connection pool
and JWT:

| Plane | Endpoint | Notes |
|-------|----------|-------|
| `flow` | `POST /core/v1/executions/flow-runs` | polls to a terminal state, resumes `WAITING` runs |
| `conversation` | `POST /core/v1/conversations` | SSE; measures TTFB and counts deltas |
| `agent` | `POST /core/v1/executions/agent-runs` | agent tool loop |
| `a2a` | `POST /core/v1/agents/{id}/a2a` | JSON-RPC 2.0 `message/send` |
| `read` | agent-runs list, agent card, health | cheap read load |

Useful flags:

```
--duration 10m          0 = run until Ctrl-C
--flow 8 --agent 4      per-plane concurrency
--conversation 2        keep low: every turn is a real OpenAI call
--unique-prompts        force semantic-cache misses (see below)
--wait-flow             execute flow runs synchronously
--no-wait-agent         enqueue agent runs instead of waiting
--json-report out.json  machine-readable final report
```

### Each worker gets its own principal

Rate limiting is keyed **per principal**, so the driver mints one JWT per worker with a distinct
`principal_id` (`stress-<plane>-<n>`). Raising concurrency raises the effective ceiling instead of
colliding with it. Workers use `principal_type: machine`; a `human` principal would force
`user_id == principal_id` on the conversation plane and collapse every virtual user into one.

### The semantic cache decides what you are actually testing

By default the driver draws from a fixed prompt pool, so after the first request of each prompt
the LLM layer serves from the semantic cache. A representative 90-second run produced **678 cache
hits against 151 real provider calls**. That is cheap and exercises the orchestration path, but it
is *not* an LLM load test.

Pass `--unique-prompts` to append a nonce to every prompt so each request misses the cache and
reaches the provider. This costs real money — check `llm_usage_ledger` before and after.

```sql
select inference_layer, count(*), round(avg(latency_ms)) as avg_ms
from llm_usage_ledger where created_at > now() - interval '10 minutes'
group by inference_layer;
```

### Preflight

Before generating load the driver checks `/health`, then fires exactly one request per enabled
plane. If any returns a setup defect — `access_policy_not_configured`, `action_not_allowed`,
`rate_limit_policy_not_published`, `billing_policy_not_active`, `missing_idempotency_key` — it
aborts and points at `prepare_stress_env.py` rather than spending ten minutes accumulating 403s.

### Correlation

Every request carries a W3C `traceparent`. `HttpTelemetryMiddleware` extracts it and makes the
server span a child, so a trace id printed in an error sample is directly searchable in Tempo.

---

## 4. Read the result

Console output reports, per route template, request count, latency p50/p95/max and the status-code
histogram. `--json-report` adds p75/p90/p99, terminal-state distributions, per-plane outcome
counters and the last 20 error samples per endpoint (each with its trace id).

Outcomes are classified rather than reduced to HTTP status, because two planes lie:

- **conversations** return HTTP 200 and report failure as a terminal SSE `error` event — the driver
  classifies on `error_code`, not on the status line;
- **A2A** always returns HTTP 200 and reports failure in the JSON-RPC `error.code`.

### Grafana

Open <http://localhost:3000> (`admin` / `admin`). Four dashboards are provisioned from
`resources/observability/grafana/`:

- **D1 Service Health (RED)** — request rate, error ratio and latency by route, span throughput by
  observation type, and a Collector-health row. If that row is unhealthy, every other panel is
  under-reporting.
- **D2 Graph Execution** — node duration and error rate, execution funnel, stuck nodes, loop
  detection, and a recent-runs table whose `trace_id` column deep-links into Tempo.
- **D3 LLM Cost and Tokens** — spend and tokens by model, task type and inference layer.
- **D4 Human SLA and Governance** — handoff and containment rates, authoring audit.

**Wait about 45 seconds after the run before trusting Prometheus.** Three intervals stack: the
application metric export (15 s), the spanmetrics flush (15 s) and the Prometheus scrape (15 s).
Tempo is much faster — assert on traces first, metrics last.

Direct backends: Tempo <http://localhost:3200>, Loki <http://localhost:3100>,
Prometheus <http://localhost:9090>, Temporal <http://localhost:8233>.

---

## 5. Metric accuracy — verified, and the trap that broke it

The span metrics are cross-checked against the driver's own request counts. Method: snapshot
`traces_span_metrics_calls_total`, run a fixed-duration burst, wait ~50 s for the pipeline, then
compare the counter delta per route against what the driver observed.

```
route                                        driver   prom delta
/core/v1/executions/flow-runs                   404          409
/core/v1/executions/agent-runs                  122          123
/core/v1/agents/{agent_id}/agent-card            73           73
/health                                         101          102
TOTAL                                           726          738   (101.7%)
```

The small excess is the driver's own preflight traffic, which runs before the timer starts.

**The trap.** This measured **22.4%** — with *negative* counter deltas — until the Collector config
was corrected. The application runs several gunicorn workers, each with its own
`service.instance.id`, so `spanmetrics` produces one independent cumulative counter per worker. The
`transform/metric_cardinality` processor was deleting `service.instance.id`, which collapsed all
those counters onto a single Prometheus series whose value flipped between workers. Prometheus read
each flip as a counter reset, so `rate()` and `increase()` silently under-reported by roughly the
worker count.

`service.instance.id` is therefore kept as a metric label. Every dashboard panel already aggregates
with `sum by (...)`, so the per-worker series combine correctly. Verify with:

```bash
curl -s -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=resets(traces_span_metrics_calls_total[10m])'
```

Any series returning non-zero means counters are colliding again.

**Rate windows are range-relative.** Panels use `[$__rate_interval]`, not a hardcoded `[5m]`, and the
`aoc-prometheus` datasource declares `timeInterval: 15s` to match `prometheus.yml`. With a fixed
`[5m]` window, a dashboard opened at its own default range (D3 is `now-30d`) computes a step far
larger than the window, so no lookback ever contains two samples and the panel renders **blank while
reporting healthy**. That is the most dangerous failure mode in this stack: an empty panel reads as
"no errors".

## 6. Tenant attribution on spans

`tenant_id` is a `spanmetrics` dimension, so it is what makes per-tenant RED possible. Coverage is
measured directly:

```
span type      coverage
http              87.9%   (remainder is /health, /docs, /openapi.json — no tenant exists)
generation       100.0%
chain            100.0%
guardrail        100.0%
retriever        100.0%
span             100.0%
agent            100.0%
conversation     100.0%
tool              97.1%
OVERALL           99.0%
```

Three mechanisms put it there:

1. `flow()` and `conversation()` bind the tenant for the whole run, and `observe()` now does the same
   whenever an observation carries `tenant_id`, `agent_run_id` or `flow_run_id` in its metadata. A
   `BoundAttributeSpanProcessor` copies bound attributes onto every descendant span that has not set
   them itself, so tagging one outer span covers its whole subtree.
2. Controllers and the agent-run service pass `metadata={"tenant_id": ...}` on their outermost
   observation, which is what carries the tenant into everything nested beneath.
3. HTTP server spans are stamped by `HttpTelemetryMiddleware`. The span opens before authentication
   runs, so the auth dependency publishes `request.state.tenant_id` and the middleware reads it back
   after the handler returns. That keeps every OpenTelemetry import inside
   `adapters/observability/`, which `tests/unit/execution/test_vendor_tracer_confinement.py` enforces.

Check coverage for any span type with:

```bash
curl -s -G http://localhost:9090/api/v1/query --data-urlencode \
  'query=sum by (aoc_observation_type) (rate(traces_span_metrics_calls_total{tenant_id=""}[5m]))'
```

## 7. Trace retention and dead deep-links

Tempo keeps 168 h (`compactor.compaction.block_retention` in `resources/observability/tempo.yaml`),
and the query frontend allows the same window so a search cannot ask for more than the store holds.
Nothing is deleted early — verify with `curl -s localhost:3200/status/config | grep block_retention`
and `tempodb_compaction_errors_total` on `:3200/metrics`.

What does bite is that **the store is younger than its retention window**. D2's recent-runs table
covers 7 days, but Tempo only holds traces since the observability stack first started, so
`trace_id` links on older rows resolve to an empty view. That is a data-age gap, not a retention
bug; it closes on its own once the stack has been up for a week.

Tempo's `metrics_generator` is limited to `local-blocks`. It previously also ran `span-metrics` and
`service-graphs`, which duplicated the Collector's `spanmetrics` connector into ~1.3k Prometheus
series that no dashboard read. The dashboards use the Collector family
(`traces_span_metrics_*`); Tempo's was `traces_spanmetrics_*` — one underscore apart, which is an
easy way to debug the wrong pipeline.

## 8. Known gaps

- The agent card advertises `url = /core/v1/a2a/agents/{id}`, which is not a registered route.
  The real path is `POST /core/v1/agents/{id}/a2a`.
- Agent-run tool calls fail with `interaction_metadata_header_missing`; the agent loop recovers and
  the run still completes, so this is only visible as `STATUS_CODE_ERROR` on `tool` spans.
- Currency figures on D3 are inflated — see the dashboard's own note.
