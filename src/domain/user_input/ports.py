from __future__ import annotations

from typing import Protocol
from uuid import UUID


class BlobStorePort(Protocol):
    async def get_bytes(self, *, tenant_id: UUID, ref: str) -> bytes:
        """Resolve ref to raw bytes for the tenant."""


class DocumentToTextPort(Protocol):
    async def to_text(self, *, data: bytes, mime_type: str, filename: str | None) -> str:
        """Convert binary document to plain/markdown text."""
