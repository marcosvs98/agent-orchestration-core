"""User input normalization (multimodal parts → single user_input)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from adapters.blob.memory_blob_store import MemoryBlobStore
from adapters.document_conversion.fake_document_to_text import FakeDocumentToText
from domain.user_input.normalizer import UserInputNormalizer
from domain.user_input.schemas import MediaRefUserInputPart, TextUserInputPart


@pytest.mark.asyncio
async def test_normalize_text_only_legacy() -> None:
    store = MemoryBlobStore()
    norm = UserInputNormalizer(store, FakeDocumentToText(), max_composed_chars=100_000)
    tid = uuid4()
    out = await norm.normalize(tenant_id=tid, user_input="hello", input_parts=None)
    assert out.user_input == "hello"


@pytest.mark.asyncio
async def test_normalize_media_ref_composes() -> None:
    tid = uuid4()
    ref = "t/assets/x.pdf"
    store = MemoryBlobStore()
    store.put(tenant_id=tid, ref=ref, data=b"%PDF-1.4 fake")
    norm = UserInputNormalizer(store, FakeDocumentToText(), max_composed_chars=100_000)
    parts = [
        MediaRefUserInputPart(type="media_ref", ref=ref, mime_type="application/pdf", filename="x.pdf"),
        TextUserInputPart(type="text", text="explain"),
    ]
    out = await norm.normalize(tenant_id=tid, user_input="explain", input_parts=parts)
    assert out.user_input
    assert "[Documento: x.pdf]" in (out.user_input or "")
    assert "explain" in (out.user_input or "")


@pytest.mark.asyncio
async def test_normalize_does_not_duplicate_user_input_already_in_parts() -> None:
    store = MemoryBlobStore()
    norm = UserInputNormalizer(store, FakeDocumentToText(), max_composed_chars=100_000)
    tid = uuid4()
    parts = [TextUserInputPart(type="text", text="hello")]
    out = await norm.normalize(tenant_id=tid, user_input="hello", input_parts=parts)
    assert out.user_input == "hello"
    assert out.user_input.count("hello") == 1


@pytest.mark.asyncio
async def test_normalize_raises_when_composed_text_exceeds_limit() -> None:
    from exceptions.service_exceptions import DomainValidationException

    store = MemoryBlobStore()
    norm = UserInputNormalizer(store, FakeDocumentToText(), max_composed_chars=5)
    tid = uuid4()
    parts = [TextUserInputPart(type="text", text="toolong")]
    with pytest.raises(DomainValidationException) as exc:
        await norm.normalize(tenant_id=tid, user_input=None, input_parts=parts)
    assert exc.value.message == "user_input_composed_too_large"


@pytest.mark.asyncio
async def test_normalize_raises_on_invalid_part_type() -> None:
    from dataclasses import dataclass

    from exceptions.service_exceptions import DomainValidationException

    @dataclass
    class UnknownPart:
        type: str = "unknown"

    store = MemoryBlobStore()
    norm = UserInputNormalizer(store, FakeDocumentToText())
    tid = uuid4()
    with pytest.raises(DomainValidationException) as exc:
        await norm.normalize(
            tenant_id=tid,
            user_input=None,
            input_parts=[UnknownPart()],  # type: ignore[list-item]
        )
    assert exc.value.message == "invalid_user_input_part"


@pytest.mark.asyncio
async def test_unsupported_mime() -> None:
    from exceptions.service_exceptions import DomainValidationException

    tid = uuid4()
    store = MemoryBlobStore()
    norm = UserInputNormalizer(store, FakeDocumentToText())
    parts = [
        MediaRefUserInputPart(
            type="media_ref",
            ref="r",
            mime_type="application/zip",
            filename="a.zip",
        ),
    ]
    with pytest.raises(DomainValidationException) as exc:
        await norm.normalize(tenant_id=tid, user_input=None, input_parts=parts)
    assert exc.value.message == "unsupported_media_mime_type"
