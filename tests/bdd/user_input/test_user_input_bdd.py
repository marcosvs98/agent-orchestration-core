"""BDD: user input normalization (domain only)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.bdd
from pytest_bdd import given, scenarios, then, when

from adapters.blob.memory_blob_store import MemoryBlobStore
from adapters.document_conversion.fake_document_to_text import FakeDocumentToText
from domain.user_input.normalizer import UserInputNormalizer

FEATURE = Path(__file__).parent / "features" / "user_input.feature"

scenarios(str(FEATURE))


@given("a tenant id")
def _tenant(bdd) -> None:
    bdd.tenant_id = uuid4()


@when('we normalize with user_input "hello world" and no input parts')
def _norm_hello(bdd) -> None:
    norm = UserInputNormalizer(MemoryBlobStore(), FakeDocumentToText(), max_composed_chars=100_000)

    async def _go() -> None:
        try:
            bdd.result = await norm.normalize(
                tenant_id=bdd.tenant_id,
                user_input="hello world",
                input_parts=None,
            )
        except Exception as exc:
            bdd.error = exc

    asyncio.run(_go())


@when('we normalize with user_input "" and no input parts')
def _norm_empty(bdd) -> None:
    norm = UserInputNormalizer(MemoryBlobStore(), FakeDocumentToText(), max_composed_chars=100_000)

    async def _go() -> None:
        try:
            bdd.result = await norm.normalize(
                tenant_id=bdd.tenant_id,
                user_input="",
                input_parts=None,
            )
        except Exception as exc:
            bdd.error = exc

    asyncio.run(_go())


@then('the composed user_input is "hello world"')
def _assert_hello(bdd) -> None:
    assert bdd.error is None
    assert bdd.result is not None
    assert bdd.result.user_input == "hello world"


@then("the composed user_input is empty")
def _assert_empty(bdd) -> None:
    assert bdd.error is None
    assert bdd.result is not None
    assert bdd.result.user_input in (None, "")
