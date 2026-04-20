from __future__ import annotations

import settings

from domain.user_input.ports import DocumentToTextPort
from exceptions.service_exceptions import DomainValidationException

from adapters.document_conversion.docling_document_to_text import DoclingDocumentToText


class DefaultDocumentToText(DocumentToTextPort):
    """text/plain UTF-8; application/pdf via Docling when enabled."""

    def __init__(self) -> None:
        self._docling = DoclingDocumentToText()

    async def to_text(self, *, data: bytes, mime_type: str, filename: str | None) -> str:
        if mime_type == "text/plain":
            return data.decode("utf-8", errors="replace")
        if mime_type == "application/pdf":
            if not settings.DOCLING_ENABLED:
                raise DomainValidationException(message="pdf_conversion_requires_docling")
            return await self._docling.to_text(data=data, mime_type=mime_type, filename=filename)
        raise DomainValidationException(message="unsupported_media_mime_type")
