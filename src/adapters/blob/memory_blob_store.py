from __future__ import annotations

from uuid import UUID

from domain.user_input.ports import BlobStorePort
from exceptions.service_exceptions import DomainValidationException


class MemoryBlobStore(BlobStorePort):
    def __init__(self, data: dict[tuple[str, str], bytes] | None = None) -> None:
        self._data = data or {}

    def put(self, *, tenant_id: UUID, ref: str, data: bytes) -> None:
        self._data[(str(tenant_id), ref)] = data

    async def get_bytes(self, *, tenant_id: UUID, ref: str) -> bytes:
        key = (str(tenant_id), ref)
        if key not in self._data:
            raise DomainValidationException(message="blob_ref_not_found")
        return self._data[key]
