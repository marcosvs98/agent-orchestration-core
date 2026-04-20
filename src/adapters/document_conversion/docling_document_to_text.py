from __future__ import annotations

import tempfile
from pathlib import Path

try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

from domain.user_input.ports import DocumentToTextPort
from exceptions.service_exceptions import DomainValidationException


class DoclingDocumentToText(DocumentToTextPort):
    """Convert documents using IBM Docling when the package is installed."""

    async def to_text(self, *, data: bytes, mime_type: str, filename: str | None) -> str:
        if DocumentConverter is None:
            raise DomainValidationException(message="docling_not_installed")

        if mime_type != "application/pdf":
            raise DomainValidationException(message="unsupported_media_mime_type")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            path = Path(tmp.name)
            converter = DocumentConverter()
            result = converter.convert(path)
            return result.document.export_to_markdown()
