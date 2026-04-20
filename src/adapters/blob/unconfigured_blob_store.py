from __future__ import annotations

from uuid import UUID

from domain.user_input.ports import BlobStorePort
from exceptions.service_exceptions import DomainValidationException


class UnconfiguredBlobStore(BlobStorePort):
    async def get_bytes(self, *, tenant_id: UUID, ref: str) -> bytes:
        raise DomainValidationException(message="blob_store_unconfigured")
