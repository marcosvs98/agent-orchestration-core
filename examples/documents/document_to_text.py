from __future__ import annotations

import asyncio
import time

from typing import Final

import settings

from adapters.document_conversion.default_document_to_text import DefaultDocumentToText
from adapters.document_conversion.docling_document_to_text import DoclingDocumentToText
from adapters.document_conversion.factory import build_document_to_text
from adapters.document_conversion.fake_document_to_text import FakeDocumentToText
from domain.user_input.ports import DocumentToTextPort
from examples.documents._pdf import handbook_pdf
from examples.support import expect, field, heading
from exceptions.service_exceptions import DomainValidationException

PLAIN: Final[bytes] = "Reimbursement policy: submit the receipt within seven days.".encode("utf-8")


async def convert(
    adapter: DocumentToTextPort,
    data: bytes,
    mime_type: str,
    filename: str | None = None,
) -> str:
    return await adapter.to_text(data=data, mime_type=mime_type, filename=filename)


async def expect_rejection(
    adapter: DocumentToTextPort,
    data: bytes,
    mime_type: str,
) -> str:
    try:
        await convert(adapter, data, mime_type)
    except DomainValidationException as exc:
        return exc.message
    raise SystemExit(f"FAILED: expected {mime_type} to be rejected")


async def main() -> None:
    print("Document to text: the DocumentToTextPort implementations")
    field("DOCLING_ENABLED", settings.DOCLING_ENABLED)
    pdf = handbook_pdf()
    field("sample pdf bytes", len(pdf))

    heading("1. The port and its three implementations")
    print("  DocumentToTextPort.to_text(data, mime_type, filename) -> str is the whole")
    print("  contract. Two consumers depend on it:")
    print("    UserInputNormalizer     media parts on a conversation turn")
    print("    RagMediaIngestService   POST /rag-configs/{id}/documents:ingestFromMedia")
    print()
    print("  FakeDocumentToText     returns a marker string; parses nothing")
    print("  DefaultDocumentToText  text/plain natively, application/pdf via Docling")
    print("  DoclingDocumentToText  IBM Docling; PDF only")

    heading("2. build_document_to_text() selects on DOCLING_ENABLED")
    selected = build_document_to_text()
    field("selected adapter", type(selected).__name__)
    expect(
        isinstance(
            selected, DefaultDocumentToText if settings.DOCLING_ENABLED else FakeDocumentToText
        ),
        "the factory follows the DOCLING_ENABLED setting",
    )
    print()
    print("  DOCLING_ENABLED defaults to false, so an unconfigured deployment silently")
    print("  gets FakeDocumentToText: every uploaded PDF becomes a marker string that is")
    print("  then chunked, embedded and stored as if it were the document. Nothing fails.")

    heading("3. FakeDocumentToText: what a misconfigured deployment stores")
    fake = FakeDocumentToText()
    marker = await convert(fake, pdf, "application/pdf", "handbook.pdf")
    field("output", repr(marker))
    expect("fake-extract" in marker, "the fake adapter returns a marker, not the document")
    expect(
        "reimbursement" not in marker,
        "none of the real document text survives - and no error is raised",
    )

    heading("4. DefaultDocumentToText: text/plain needs no Docling")
    default = DefaultDocumentToText()
    text = await convert(default, PLAIN, "text/plain", "policy.txt")
    field("output", repr(text))
    expect(text == PLAIN.decode("utf-8"), "text/plain is decoded as UTF-8, verbatim")

    invalid_utf8 = b"caf\xff resume"
    lenient = await convert(default, invalid_utf8, "text/plain", "broken.txt")
    field("invalid utf-8 input", repr(lenient))
    print("  Decoding uses errors='replace', so malformed bytes become U+FFFD instead of")
    print("  failing the ingest. The corpus keeps the damage silently.")

    heading("5. Unsupported media types are rejected")
    for mime_type in ("image/png", "application/msword", "text/html"):
        message = await expect_rejection(default, b"whatever", mime_type)
        field(mime_type, message)
    print()
    print("  The supported set is exactly {text/plain, application/pdf}. UserInputNormalizer")
    print("  enforces the same pair before it ever reaches the converter.")

    if not settings.DOCLING_ENABLED:
        heading("6. PDF without Docling")
        message = await expect_rejection(default, pdf, "application/pdf")
        field("application/pdf", message)
        expect(
            message == "pdf_conversion_requires_docling",
            "DefaultDocumentToText refuses PDF when DOCLING_ENABLED is false",
        )
        print()
        print("  Re-run with DOCLING_ENABLED=true to see the real conversion:")
        print(
            "    DOCLING_ENABLED=true PYTHONPATH=src uv run python -m examples.documents.document_to_text"
        )
        print()
        print("Done.")
        return

    heading("6. Docling converts the PDF to markdown")
    print("  First call in a fresh process loads ML model weights - expect 20-30 seconds")
    print("  cold, ~1 second warm. Docling ships in the optional `docling` extra:")
    print("    uv sync --extra docling")
    docling = DoclingDocumentToText()
    started = time.perf_counter()
    markdown = await convert(docling, pdf, "application/pdf", "handbook.pdf")
    field("elapsed", f"{time.perf_counter() - started:.1f}s")
    field("output", repr(markdown[:76]))
    expect("reimbursement" in markdown, "the real document text was extracted")
    expect(
        "USD 120" in markdown,
        "including body lines, not just the heading",
    )
    print()
    print("  export_to_markdown() is what lands in rag_document.content, so the chunker")
    print("  sees markdown - a good reason to prefer RECURSIVE_CHARACTER with '\\n\\n' as the")
    print("  first separator for PDF corpora.")

    heading("7. Conversion runs off the event loop")
    print("  converter.convert() is synchronous and CPU-bound. to_text hands it to")
    print("  asyncio.to_thread, so the API keeps serving other requests while a PDF is")
    print("  being parsed.")

    ticks = 0
    stop = asyncio.Event()

    async def heartbeat() -> None:
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(0.05)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    started = time.perf_counter()
    await convert(docling, pdf, "application/pdf", "handbook.pdf")
    elapsed = time.perf_counter() - started
    stop.set()
    await beat

    field("conversion", f"{elapsed:.1f}s")
    field("heartbeat ticks", f"{ticks} (a free loop would tick ~{int(elapsed / 0.05)})")
    expect(ticks > 0, "the event loop kept running during the conversion")
    print()
    print("  This adapter used to await the converter directly on the loop, which froze")
    print("  the whole process for the duration of every PDF. See")
    print("  tests/unit/adapters/test_docling_document_to_text.py.")

    heading("8. Cost per call")
    started = time.perf_counter()
    await convert(docling, pdf, "application/pdf", "handbook.pdf")
    warm = time.perf_counter() - started
    field("warm call", f"{warm:.1f}s")
    print("  DocumentConverter is constructed inside every call, so each conversion pays")
    print("  the setup cost again. That is what keeps the adapter thread-safe under")
    print("  asyncio.to_thread, but it puts a floor of roughly a second on every PDF.")

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
