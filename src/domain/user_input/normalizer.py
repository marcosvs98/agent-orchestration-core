from __future__ import annotations

import time
from uuid import UUID

import settings

from adapters.observability.logging import get_logger
from domain.execution.schemas.execution import FlowRunInput
from domain.user_input.ports import BlobStorePort, DocumentToTextPort
from domain.user_input.schemas import (
    MediaRefUserInputPart,
    TextUserInputPart,
    UserInputPart,
)
from exceptions.service_exceptions import DomainValidationException

logger = get_logger(__name__)

_SUPPORTED_MEDIA = frozenset({"application/pdf", "text/plain"})


class UserInputNormalizer:
    """Normalize optional text + input_parts into FlowRunInput with only user_input set."""

    def __init__(
        self,
        blob_store: BlobStorePort,
        document_to_text: DocumentToTextPort,
        *,
        max_composed_chars: int | None = None,
    ) -> None:
        self._blob_store = blob_store
        self._document_to_text = document_to_text
        self._max_composed_chars = max_composed_chars or settings.USER_INPUT_COMPOSED_MAX_CHARS

    async def normalize(
        self,
        *,
        tenant_id: UUID,
        user_input: str | None,
        input_parts: list[UserInputPart] | None,
    ) -> FlowRunInput:
        if not input_parts:
            return FlowRunInput(user_input=user_input)

        started = time.perf_counter()
        chunks: list[str] = []
        for part in input_parts:
            if isinstance(part, TextUserInputPart):
                if part.text.strip():
                    chunks.append(part.text)
            elif isinstance(part, MediaRefUserInputPart):
                if part.mime_type not in _SUPPORTED_MEDIA:
                    raise DomainValidationException(message="unsupported_media_mime_type")
                data = await self._blob_store.get_bytes(tenant_id=tenant_id, ref=part.ref)
                text = await self._document_to_text.to_text(
                    data=data,
                    mime_type=part.mime_type,
                    filename=part.filename,
                )
                label = part.filename or part.ref
                chunks.append(f"[Documento: {label}]\n---\n{text}\n---")
            else:
                raise DomainValidationException(message="invalid_user_input_part")

        composed = "\n\n".join(chunks).strip()
        extra = (user_input or "").strip()
        if extra:
            if extra not in composed:
                composed = f"{composed}\n\n{extra}".strip() if composed else extra

        if len(composed) > self._max_composed_chars:
            raise DomainValidationException(message="user_input_composed_too_large")

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "user_input_normalized",
            tenant_id=str(tenant_id),
            duration_ms=elapsed_ms,
            parts_count=len(input_parts),
        )
        return FlowRunInput(user_input=composed or None)
