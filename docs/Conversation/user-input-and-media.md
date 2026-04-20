# User input and media (multimodal)

## Purpose

Clients can send **typed parts** (`text` and `media_ref`) alongside the legacy `user_input` string. The service **normalizes** all parts into a **single canonical string** stored as `flow_run.input.user_input` only. Conversion metadata (converter id, duration, hashes) is **not** exposed in API responses or persisted input JSON—use structured logs/traces for operations.

## Request shape

- **`user_input`**: optional free-text (unchanged from legacy).
- **`input_parts`**: optional list of discriminated objects:
  - `{ "type": "text", "text": "..." }`
  - `{ "type": "media_ref", "ref": "...", "mime_type": "application/pdf", "filename": "..." | null }`

`ref` is a **tenant-scoped opaque key** resolved by the configured blob store. The default deployment ships with **no blob backend** wired (`blob_store_unconfigured` until you plug storage).

## Supported MIME types (initial)

- `text/plain`
- `application/pdf` (when `DOCLING_ENABLED=true` and the `docling` extra is installed; otherwise use the fake converter in tests or enable Docling for production)

## Persistence

`flow_run.input` JSON contains **only**:

```json
{ "user_input": "<composed text>" }
```

## Related

- [SSE and runtime](sse-and-runtime.md)
- [RAG runtime — ingest from media](../RAG/runtime-and-integration.md#ingest-from-media)
