from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from domain.context.schemas.memory_retrieval import TemporalTimestampSource
from domain.context.services.memory_retrieval import MemoryRetrievalService
from domain.rag.schemas.rag import RagContext, RagContextItem, RagContextReason


def test_rerank_with_temporal_decay_prefers_newer_observed_at() -> None:
    svc = MemoryRetrievalService(
        tenant_knowledge_retriever=None,
        user_memory_reader=None,
        session_context_service=None,
        tracer=MagicMock(),
    )
    now = datetime.now(UTC)
    older = now - timedelta(days=30)
    d1, d2 = uuid4(), uuid4()
    rag = RagContext(
        context_items=[
            RagContextItem(
                document_id=d1,
                chunk_id=d1,
                content="older",
                score=1.0,
                observed_at=older,
            ),
            RagContextItem(
                document_id=d2,
                chunk_id=d2,
                content="newer",
                score=1.0,
                observed_at=now,
            ),
        ],
        eligible=True,
        reason=RagContextReason.OK,
    )
    out = svc._rerank_with_temporal_decay(
        rag_context=rag,
        base_top_k=1,
        timestamp_source=TemporalTimestampSource.OBSERVED_AT,
        half_life_seconds=86_400,
    )
    assert len(out.context_items) == 1
    assert out.context_items[0].content == "newer"
