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

!!! warning "The shipped wiring cannot resolve a media ref"
    `containers.py` binds `blob_store` to `UnconfiguredBlobStore`, which raises
    `blob_store_unconfigured` for every ref, and no endpoint writes bytes into a blob store. Media
    parts therefore fail in a default deployment until a real `BlobStorePort` is bound. With
    `DOCLING_ENABLED=false` the converter is `FakeDocumentToText`, which returns a marker string
    for a PDF **without raising** — the marker then flows into the prompt as if it were the
    document. See [Known limitations](../Develop/limitations.md).

## Related

- `examples/documents/` (repository root) — both pipelines run end to end against an in-memory blob store, plus the Docling conversion itself
- [SSE and runtime](sse-and-runtime.md)
- [RAG runtime — ingest from media](../RAG/runtime-and-integration.md#ingest-from-media)
