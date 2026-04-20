from __future__ import annotations

import settings

from adapters.document_conversion.default_document_to_text import DefaultDocumentToText
from adapters.document_conversion.fake_document_to_text import FakeDocumentToText
from domain.user_input.ports import DocumentToTextPort


def build_document_to_text() -> DocumentToTextPort:
    if settings.DOCLING_ENABLED:
        return DefaultDocumentToText()
    return FakeDocumentToText()
