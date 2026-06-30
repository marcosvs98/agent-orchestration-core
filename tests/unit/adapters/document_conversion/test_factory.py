from __future__ import annotations

import pytest

import settings
from adapters.document_conversion.default_document_to_text import DefaultDocumentToText
from adapters.document_conversion.factory import build_document_to_text
from adapters.document_conversion.fake_document_to_text import FakeDocumentToText


def test_build_document_to_text_uses_fake_when_docling_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DOCLING_ENABLED", False)
    assert isinstance(build_document_to_text(), FakeDocumentToText)


def test_build_document_to_text_uses_default_when_docling_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DOCLING_ENABLED", True)
    assert isinstance(build_document_to_text(), DefaultDocumentToText)
