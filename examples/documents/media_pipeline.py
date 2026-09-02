from __future__ import annotations

import asyncio
from typing import Any, Dict, Final, List, Sequence, Tuple
from uuid import UUID, uuid4

import settings

from adapters.blob.memory_blob_store import MemoryBlobStore
from adapters.blob.unconfigured_blob_store import UnconfiguredBlobStore
from adapters.document_conversion.factory import build_document_to_text
from domain.rag.services.rag_media_ingest_service import RagMediaIngestService
from domain.rag.schemas.rag import RagDocumentCreate, RagIngestFromMediaRequest
from domain.user_input.normalizer import UserInputNormalizer
from domain.user_input.schemas import MediaRefUserInputPart, TextUserInputPart
from examples.documents._pdf import handbook_pdf
from examples.support import expect, field, heading
from exceptions.service_exceptions import DomainValidationException

TENANT_ID: Final[UUID] = UUID("00000000-0000-0000-0000-0000000000aa")
PDF_REF: Final[str] = "blob://tenant/handbook.pdf"
TXT_REF: Final[str] = "blob://tenant/notice.txt"
NOTICE: Final[bytes] = "Notice: the card statement closes on the 25th.".encode("utf-8")


class RecordingRuntime:
    def __init__(self) -> None:
        self.batches: List[Dict[str, Any]] = []

    async def ingest_documents_batch(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        documents: Sequence[RagDocumentCreate],
    ) -> Tuple[int, int]:
        self.batches.append(
            {
                "tenant_id": tenant_id,
                "rag_config_id": rag_config_id,
                "documents": documents,
            }
        )
        return len(documents), 0


def blob_store() -> MemoryBlobStore:
    store = MemoryBlobStore()
    store.put(tenant_id=TENANT_ID, ref=PDF_REF, data=handbook_pdf())
    store.put(tenant_id=TENANT_ID, ref=TXT_REF, data=NOTICE)
    return store


async def main() -> None:
    print("The two pipelines that turn an uploaded document into text")
    field("DOCLING_ENABLED", settings.DOCLING_ENABLED)
    converter = build_document_to_text()
    field("converter", type(converter).__name__)
    if not settings.DOCLING_ENABLED:
        print()
        print("  Docling is off, so PDFs below resolve through FakeDocumentToText and the")
        print("  extracted text is a marker. Re-run with DOCLING_ENABLED=true for real text.")

    heading("1. Conversation input: UserInputNormalizer")
    print("  A turn may carry input_parts instead of a plain user_input. Each media part")
    print("  is resolved from the blob store, converted to text, wrapped in a labelled")
    print("  block, and concatenated into a single user_input string.")
    normalizer = UserInputNormalizer(blob_store=blob_store(), document_to_text=converter)

    composed = await normalizer.normalize(
        tenant_id=TENANT_ID,
        user_input="Summarize the reimbursement rules.",
        input_parts=[
            MediaRefUserInputPart(
                ref=PDF_REF, mime_type="application/pdf", filename="handbook.pdf"
            ),
            TextUserInputPart(text="Focus on the meal allowance section."),
        ],
    )
    text = composed.user_input or ""
    field("composed chars", len(text))
    print("      " + text[:150].replace("\n", "\\n"))
    expect("[Documento: handbook.pdf]" in text, "each media part is labelled in the prompt")
    expect(
        "Focus on the meal allowance section." in text,
        "text parts are concatenated alongside the converted document",
    )
    expect(
        "Summarize the reimbursement rules." in text,
        "the plain user_input is appended after the parts",
    )
    print()
    print("  The result is ONE string. Downstream nodes never learn that a PDF was")
    print("  involved - moderation, tool selection and slot filling all see prompt text,")
    print("  and the document is billed as input tokens on every LLM call of that turn.")

    heading("2. Bounds and rejections")
    tiny = UserInputNormalizer(
        blob_store=blob_store(),
        document_to_text=converter,
        max_composed_chars=40,
    )
    try:
        await tiny.normalize(
            tenant_id=TENANT_ID,
            user_input=None,
            input_parts=[
                MediaRefUserInputPart(ref=PDF_REF, mime_type="application/pdf", filename="h.pdf")
            ],
        )
        raise SystemExit("FAILED: expected the composed-size guard to fire")
    except DomainValidationException as exc:
        field("over max_composed_chars", exc.message)
    print(
        f"      the real limit is USER_INPUT_COMPOSED_MAX_CHARS={settings.USER_INPUT_COMPOSED_MAX_CHARS}"
    )

    try:
        await normalizer.normalize(
            tenant_id=TENANT_ID,
            user_input=None,
            input_parts=[
                MediaRefUserInputPart(ref=PDF_REF, mime_type="image/png", filename="x.png")
            ],
        )
        raise SystemExit("FAILED: expected an unsupported mime type to be rejected")
    except DomainValidationException as exc:
        field("image/png part", exc.message)

    try:
        await normalizer.normalize(
            tenant_id=TENANT_ID,
            user_input=None,
            input_parts=[
                MediaRefUserInputPart(
                    ref="blob://tenant/missing.pdf",
                    mime_type="application/pdf",
                    filename="missing.pdf",
                )
            ],
        )
        raise SystemExit("FAILED: expected an unknown ref to be rejected")
    except DomainValidationException as exc:
        field("unknown blob ref", exc.message)

    heading("3. RAG ingest: RagMediaIngestService")
    print("  documents:ingestFromMedia resolves the ref, converts it, and hands ONE")
    print("  RagDocumentCreate to the same batch ingest the JSON endpoint uses.")
    runtime = RecordingRuntime()
    service = RagMediaIngestService(
        runtime_service=runtime,
        blob_store=blob_store(),
        document_to_text=converter,
    )
    rag_config_id = uuid4()
    accepted = await service.schedule_ingest_from_media(
        tenant_id=TENANT_ID,
        rag_config_id=rag_config_id,
        body=RagIngestFromMediaRequest(
            source="handbook",
            doc_type="policy_reimbursement",
            metadata={"topic": "reimbursement"},
            media_ref=PDF_REF,
            mime_type="application/pdf",
        ),
    )
    field("status", accepted.status)
    field("accepted_count", accepted.accepted_count)
    await asyncio.sleep(0.2)

    expect(len(runtime.batches) == 1, "one batch reached the runtime service")
    document = runtime.batches[0]["documents"][0]
    field("document.source", document.source)
    field("document.doc_type", document.doc_type)
    field("document.pages", document.pages)
    field("document.content", repr(document.content[:64]))
    expect(document.pages is None, "media ingest never sets `pages`")
    print()
    print("  That last line is the PER_PAGE trap: the media endpoint produces a single")
    print("  content string, so a rag_config whose chunking rule is PER_PAGE will reject")
    print("  every media-ingested document with rag_per_page_pages_required. Use")
    print("  TOKEN_WINDOW or RECURSIVE_CHARACTER for media corpora, or pre-split and post")
    print("  to documents:ingest with an explicit `pages` array.")

    heading("4. Response is 202 before any of that happens")
    print("  schedule_ingest_from_media converts synchronously, then fires the batch as a")
    print("  background task whose exceptions are swallowed. The caller is told ACCEPTED")
    print("  and never learns whether chunking or embedding succeeded - poll")
    print("  GET /core/v1/rag-documents and check embedding_status instead.")

    heading("5. The shipped wiring cannot serve this endpoint")
    unconfigured = RagMediaIngestService(
        runtime_service=RecordingRuntime(),
        blob_store=UnconfiguredBlobStore(),
        document_to_text=converter,
    )
    try:
        await unconfigured.schedule_ingest_from_media(
            tenant_id=TENANT_ID,
            rag_config_id=rag_config_id,
            body=RagIngestFromMediaRequest(
                source="handbook",
                doc_type="policy_reimbursement",
                metadata={"topic": "reimbursement"},
                media_ref=PDF_REF,
                mime_type="application/pdf",
            ),
        )
        raise SystemExit("FAILED: expected the unconfigured blob store to reject the call")
    except DomainValidationException as exc:
        field("UnconfiguredBlobStore", exc.message)
        expect(
            exc.message == "blob_store_unconfigured",
            "the shipped blob store refuses every ref",
        )
    print()
    print("  containers.py binds blob_store to UnconfiguredBlobStore, and nothing writes")
    print("  bytes into a store over HTTP. So POST documents:ingestFromMedia returns")
    print("  400 blob_store_unconfigured in a default deployment, and conversation media")
    print("  parts fail the same way. Both pipelines are complete except for their")
    print("  storage adapter - bind a real BlobStorePort to switch them on.")

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
