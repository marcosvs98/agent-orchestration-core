from __future__ import annotations

from domain.user_input.ports import DocumentToTextPort


class FakeDocumentToText(DocumentToTextPort):
    """Returns a fixed marker; does not parse PDF."""

    async def to_text(self, *, data: bytes, mime_type: str, filename: str | None) -> str:
        name = filename or "blob"
        return f"[fake-extract:{mime_type}:{name}:len={len(data)}]"
