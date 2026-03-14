from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer


class _FakeTracer:
    def observe(self, *, as_type, name, input):
        return contextlib.nullcontext()


@pytest.mark.asyncio
async def test_index_document_ingests_with_tool_catalog_metadata():
    tenant_id = uuid4()
    tool_id = uuid4()
    tool_config_id = uuid4()
    rag_config_id = uuid4()
    rag_runtime_service = MagicMock()
    rag_runtime_service.ingest_document = AsyncMock()
    rag_repository = MagicMock()
    rag_repository.list_rag_configs = AsyncMock(
        return_value=[SimpleNamespace(rag_config_id=rag_config_id)]
    )
    indexer = ToolCatalogIndexer(
        rag_runtime_service=rag_runtime_service,
        rag_repository=rag_repository,
        tracer=_FakeTracer(),
    )
    document = indexer.build_document(
        tool_id=tool_id,
        tool_config_id=tool_config_id,
        tool_name="charges",
        config={
            "path": "/v1/charges",
            "method": "POST",
            "operation_id": "createCharge",
            "summary": "Create charge",
            "description": "Creates a new charge",
            "request_schema": {"type": "object"},
            "response_schema": {"type": "object"},
            "examples": ['{"amount":100}'],
        },
        version="1.0.0",
    )

    indexed = await indexer.index_document(
        tenant_id=tenant_id,
        document=document,
    )

    assert indexed is True
    rag_runtime_service.ingest_document.assert_called_once()
    _, kwargs = rag_runtime_service.ingest_document.call_args
    payload = kwargs["document"]
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["rag_config_id"] == rag_config_id
    assert payload.source == "tool_catalog"
    assert payload.doc_type == "tool_catalog"
    assert payload.metadata["tool_config_id"] == str(tool_config_id)
    assert "createCharge" in payload.content


@pytest.mark.asyncio
async def test_index_document_returns_false_when_no_published_rag_config():
    rag_runtime_service = MagicMock()
    rag_runtime_service.ingest_document = AsyncMock()
    rag_repository = MagicMock()
    rag_repository.list_rag_configs = AsyncMock(return_value=[])
    indexer = ToolCatalogIndexer(
        rag_runtime_service=rag_runtime_service,
        rag_repository=rag_repository,
        tracer=_FakeTracer(),
    )
    document = indexer.build_document(
        tool_id=uuid4(),
        tool_config_id=uuid4(),
        tool_name="charges",
        config={},
        version="1.0.0",
    )

    indexed = await indexer.index_document(
        tenant_id=uuid4(),
        document=document,
    )

    assert indexed is False
    rag_runtime_service.ingest_document.assert_not_called()
