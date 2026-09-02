import asyncio
import time

import pytest

from adapters.document_conversion import docling_document_to_text as module
from adapters.document_conversion.docling_document_to_text import DoclingDocumentToText
from exceptions.service_exceptions import DomainValidationException

PDF_BYTES = b"%PDF-1.4 fake"
BLOCKING_SECONDS = 0.3


class _FakeDocument:
    @staticmethod
    def export_to_markdown() -> str:
        return "# extracted"


class _FakeResult:
    document = _FakeDocument()


class _BlockingConverter:
    def convert(self, path):
        time.sleep(BLOCKING_SECONDS)
        return _FakeResult()


@pytest.fixture
def blocking_converter(monkeypatch):
    monkeypatch.setattr(module, "DocumentConverter", _BlockingConverter)


@pytest.mark.asyncio
async def test_converts_pdf_to_markdown(blocking_converter):
    result = await DoclingDocumentToText().to_text(
        data=PDF_BYTES, mime_type="application/pdf", filename="doc.pdf"
    )

    assert result == "# extracted"


@pytest.mark.asyncio
async def test_conversion_does_not_block_the_event_loop(blocking_converter):
    ticks = 0
    stop = asyncio.Event()

    async def heartbeat() -> None:
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    await DoclingDocumentToText().to_text(
        data=PDF_BYTES, mime_type="application/pdf", filename="doc.pdf"
    )
    stop.set()
    await beat

    assert ticks > 5


@pytest.mark.asyncio
async def test_conversions_run_concurrently(blocking_converter):
    started = time.perf_counter()

    await asyncio.gather(
        *[
            DoclingDocumentToText().to_text(
                data=PDF_BYTES, mime_type="application/pdf", filename="doc.pdf"
            )
            for _ in range(3)
        ]
    )

    assert time.perf_counter() - started < BLOCKING_SECONDS * 3


@pytest.mark.asyncio
async def test_rejects_non_pdf_mime_types(blocking_converter):
    with pytest.raises(DomainValidationException) as exc:
        await DoclingDocumentToText().to_text(
            data=b"hello", mime_type="text/plain", filename="a.txt"
        )

    assert exc.value.message == "unsupported_media_mime_type"


@pytest.mark.asyncio
async def test_reports_a_missing_docling_install(monkeypatch):
    monkeypatch.setattr(module, "DocumentConverter", None)

    with pytest.raises(DomainValidationException) as exc:
        await DoclingDocumentToText().to_text(
            data=PDF_BYTES, mime_type="application/pdf", filename="doc.pdf"
        )

    assert exc.value.message == "docling_not_installed"
