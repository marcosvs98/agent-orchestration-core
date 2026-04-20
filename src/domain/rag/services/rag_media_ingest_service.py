from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from domain.rag.schemas.rag import (
    RagDocumentCreate,
    RagDocumentsIngestBatchAccepted,
    RagIngestFromMediaRequest,
)
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.user_input.ports import BlobStorePort, DocumentToTextPort


class RagMediaIngestService:
    def __init__(
        self,
        runtime_service: RagRuntimeService,
        blob_store: BlobStorePort,
        document_to_text: DocumentToTextPort,
    ) -> None:
        self._runtime = runtime_service
        self._blob_store = blob_store
        self._document_to_text = document_to_text

    async def schedule_ingest_from_media(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: UUID,
        body: RagIngestFromMediaRequest,
    ) -> RagDocumentsIngestBatchAccepted:
        raw = await self._blob_store.get_bytes(tenant_id=tenant_id, ref=body.media_ref)
        text = await self._document_to_text.to_text(
            data=raw,
            mime_type=body.mime_type,
            filename=None,
        )
        document = RagDocumentCreate(
            source=body.source,
            doc_type=body.doc_type,
            content=text,
            metadata=dict(body.metadata),
            rag_config_id=rag_config_id,
        )
        job_id = uuid4()
        accepted = RagDocumentsIngestBatchAccepted(
            rag_config_id=rag_config_id,
            job_id=job_id,
            accepted_count=1,
        )

        async def _run() -> None:
            try:
                await self._runtime.ingest_documents_batch(
                    tenant_id=tenant_id,
                    rag_config_id=rag_config_id,
                    documents=[document],
                )
            except Exception:
                pass

        asyncio.create_task(_run())
        return accepted
