from __future__ import annotations

from uuid import uuid4

import pytest

from adapters.blob.memory_blob_store import MemoryBlobStore
from adapters.blob.unconfigured_blob_store import UnconfiguredBlobStore
from exceptions.service_exceptions import DomainValidationException


@pytest.mark.asyncio
async def test_memory_blob_store_raises_when_ref_missing() -> None:
    store = MemoryBlobStore()
    with pytest.raises(DomainValidationException) as exc_info:
        await store.get_bytes(tenant_id=uuid4(), ref="missing")
    assert exc_info.value.message == "blob_ref_not_found"


@pytest.mark.asyncio
async def test_unconfigured_blob_store_raises() -> None:
    store = UnconfiguredBlobStore()
    with pytest.raises(DomainValidationException) as exc_info:
        await store.get_bytes(tenant_id=uuid4(), ref="any")
    assert exc_info.value.message == "blob_store_unconfigured"
