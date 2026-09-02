# Known limitations

Things that do not work the way you would reasonably assume, written down before you discover them
in production. None of these is a secret; all of them are things we would want to know before
adopting someone else's orchestration engine.

This page covers limitations that are real and disclosed. It is not a defect list and it is not a
security advisory — for reporting a vulnerability, see `SECURITY.md` at the repository root.

## Rate limiting stops enforcing when the cache is unreachable

Rate limits and cost guardrails are both counted in Redis, but they fail in opposite directions.

`CACHE_SILENT_MODE` defaults to `true`, so a Redis failure is absorbed rather than raised and the
request proceeds. `RateLimitService` reads its counter straight through that wrapper, so while Redis
is down **rate limiting is not enforced at all** — every caller is under the limit.

Spend and call guardrails are not affected. `GuardrailEngine` raises
`GuardrailUnavailableException` (503) whenever a counter cannot be read or written, including the
`False` that silent mode substitutes for a failed increment. A budget that cannot be read must not
read as zero, so that path is deliberately fail-closed regardless of `CACHE_SILENT_MODE`.

Set `CACHE_SILENT_MODE=false` if you would rather fail requests than run unmetered on the rate-limit
path too. That setting is global: it makes every cache dependency hard, not only the limiters.

## Outbound tool calls are not restricted by destination

A tool config names an HTTP endpoint and the runtime calls it. There is no egress allowlist, no
private-address filter, and redirects are followed with the resolved credentials still attached. A
tenant who can author a tool config can therefore direct an authenticated request anywhere the
service's network can reach, and an upstream that starts returning redirects can move a tenant's
credential to a destination the tenant did not name.

If you run this where tenants are not fully trusted, put the outbound path behind an egress proxy
you control.

## An upstream error is recorded as a successful tool run

`HttpToolExecutor` does not raise on a 4xx or 5xx response. A tool call that returns `503` is
written as a completed run with a successful status.

Three things follow from that. The retry path and the human-escalation path never trigger for HTTP
errors — the most common upstream failure there is. The response builder renders the error body as
though it were a result. And the run is counted and billed as successful.

This is deliberate rather than pending: what counts as a successful tool run feeds billing policy,
circuit breakers and idempotency, so changing it is a product decision. Transport errors — a hang-up,
a timeout, a refused connection — *are* classified correctly, so a stub that closes the connection
exercises the failure paths that a `503` does not.

## Authoring authorization is effectively tenant-level

There is a scope taxonomy, and tokens carry scopes. Almost no authoring endpoint checks them. In
practice any principal holding a valid token for a tenant can perform any authoring action on that
tenant: create flows, publish versions, change policies.

Tenant isolation and authoring granularity are different questions, and only the first is enforced
on those paths. If you need per-role separation inside a tenant, enforce it in front of this
service.

## Document ingestion deduplicates across configurations and users

Ingestion deduplicates on tenant plus content hash — not on RAG configuration, not on user. Two
consequences:

- Identical content submitted under a different source, type, version or user collapses into one
  row, and the first writer's ownership metadata is the one retrieval filters on.
- Content that already exists anywhere else in the tenant is silently not added to the new
  configuration, which can then never retrieve it. This happens behind a `202 Accepted`.

Shared boilerplate belongs to whichever configuration ingested it first. If two configurations need
the same text, vary the content or keep them in separate tenants.

## The document pipelines need an adapter you have to supply

The blob store ships unconfigured. `POST /rag-configs/{id}/documents:ingestFromMedia` and
conversation media parts both fail with `blob_store_unconfigured` until you bind a real
implementation. The pipelines themselves are complete — `examples/documents/media_pipeline.py`
runs them end to end against an in-memory store — so this is a missing binding rather than missing
functionality.

Related, and more dangerous: text extraction is disabled by default. With `DOCLING_ENABLED=false`
the extractor returns a placeholder marker instead of raising, and that marker is then chunked,
embedded and stored as if it were the document. A deployment that configures blob storage but
forgets the extractor builds a corpus of markers and gets no error saying so. Enable both together.

## Where this sits

These are the limitations we consider material to an adoption decision. Correctness defects that
do not change how you would deploy the system are tracked privately and fixed in the ordinary way.
