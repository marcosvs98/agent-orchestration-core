# Document-to-text examples

How an uploaded PDF or text file becomes prompt text or a RAG corpus, and what the shipped
configuration actually does with it.

| Example | Infra | Covers |
|---------|-------|--------|
| `document_to_text` | none | The three `DocumentToTextPort` adapters, the `DOCLING_ENABLED` switch, mime-type guards, and real Docling conversion |
| `media_pipeline` | none | The two consumers — `UserInputNormalizer` and `RagMediaIngestService` — and the blob-store gap |

```bash
PYTHONPATH=src uv run python -m examples.documents.document_to_text
PYTHONPATH=src uv run python -m examples.documents.media_pipeline
```

Both run without Docling and report the degraded path. To exercise real PDF conversion:

```bash
uv sync --extra docling
DOCLING_ENABLED=true PYTHONPATH=src uv run python -m examples.documents.document_to_text
DOCLING_ENABLED=true PYTHONPATH=src uv run python -m examples.documents.media_pipeline
```

The sample PDF is generated in-process by `examples/documents/_pdf.py` — no fixture file, no
download.

## The contract

`DocumentToTextPort` is one method:

```python
async def to_text(self, *, data: bytes, mime_type: str, filename: str | None) -> str
```

Three implementations, selected by `build_document_to_text()`:

| Adapter | `text/plain` | `application/pdf` | Anything else |
|---------|--------------|-------------------|---------------|
| `FakeDocumentToText` | marker string | marker string | marker string |
| `DefaultDocumentToText` | UTF-8 decode | delegates to Docling | `unsupported_media_mime_type` |
| `DoclingDocumentToText` | `unsupported_media_mime_type` | markdown via IBM Docling | `unsupported_media_mime_type` |

`DOCLING_ENABLED` (default **false**) picks `DefaultDocumentToText` when true and
`FakeDocumentToText` when false.

## Two consumers

**`UserInputNormalizer`** — a conversation turn may send `input_parts` instead of `user_input`.
Each `MediaRefUserInputPart` is resolved from the blob store, converted, wrapped as
`[Documento: <name>]\n---\n<text>\n---`, and joined into a single `user_input` string bounded by
`USER_INPUT_COMPOSED_MAX_CHARS`.

Downstream nodes never learn a PDF was involved: moderation, tool selection, slot filling and
response rendering all see one prompt string — and the document is billed as input tokens on
**every** LLM call of that turn.

**`RagMediaIngestService`** — `POST /core/v1/rag-configs/{id}/documents:ingestFromMedia` resolves
the ref, converts it, and hands one `RagDocumentCreate` to the same batch ingest the JSON endpoint
uses. Conversion happens *before* the response; chunking and embedding happen in a fire-and-forget
task whose exceptions are swallowed, so a `202 ACCEPTED` says nothing about whether the document
was stored. Poll `GET /core/v1/rag-documents` and check `embedding_status`.

## Things worth knowing

**`DOCLING_ENABLED=false` is not a failure mode — it is a silent one.** The factory returns
`FakeDocumentToText`, whose output for a PDF is `[fake-extract:application/pdf:handbook.pdf:len=889]`.
That marker is then chunked, embedded and stored as if it were the document. No exception, no log,
a corpus full of markers. `DefaultDocumentToText` is the adapter that raises
`pdf_conversion_requires_docling`; the fake one never does.

**Media ingest never sets `pages`.** A `rag_config` whose chunking rule is `PER_PAGE` rejects every
media-ingested document with `rag_per_page_pages_required`. Use `TOKEN_WINDOW` or
`RECURSIVE_CHARACTER` for media corpora, or pre-split and post to `documents:ingest` with an
explicit `pages` array.

**Docling emits markdown.** `export_to_markdown()` is what lands in `rag_document.content`, which
is a good argument for `RECURSIVE_CHARACTER` with `"\n\n"` as the first separator on PDF corpora —
see [`examples/rag/chunking_strategies.py`](../rag/chunking_strategies.py).

**`text/plain` decoding is lenient.** `errors="replace"` means malformed bytes become U+FFFD rather
than failing the ingest, so encoding damage is stored silently.

**Docling is an optional extra and is slow.** `uv sync --extra docling`. The first conversion in a
process loads ML model weights (20–30s cold, ~1s warm), and `DocumentConverter` is constructed on
every call, which puts a floor of roughly a second on each PDF.

## Known defects these examples surface

Written up in [Known limitations](../../docs/Develop/limitations.md).

**Fixed here — PDF conversion froze the whole API process.** `DoclingDocumentToText.to_text` was
`async def` but called the synchronous, CPU-bound `converter.convert()` directly on the event loop.
Measured with a heartbeat coroutine: **0 ticks** during a 2.2s conversion where a free loop would
have ticked 43 times. Every other request, health check and SSE stream stalled for the duration of
every PDF — seconds for a trivial one-page file, minutes for a scanned document. The call now runs
through `asyncio.to_thread`; the same measurement gives 36/38 ticks. Regression tests in
`tests/unit/adapters/test_docling_document_to_text.py`, two of which fail against the old code.

**Open — the shipped wiring cannot serve either pipeline.** `containers.py` binds `blob_store` to
`UnconfiguredBlobStore`, which raises `blob_store_unconfigured` for every ref, and no endpoint
writes bytes into a blob store. Confirmed against a running service:

```
POST /core/v1/rag-configs/{id}/documents:ingestFromMedia
→ 400 {"code":"DOMAIN_VALIDATION","message":"blob_store_unconfigured"}
```

Conversation media parts fail identically. Both pipelines are complete except for their storage
adapter — binding a real `BlobStorePort` switches them on.
