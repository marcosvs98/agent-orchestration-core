from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.context.services.memory_writer import MemoryWriteService
from domain.governance.schemas.memory_policy import (
    AllowedSchema,
    MemoryPolicyDefinition,
    MemoryPolicySource,
    MemoryWriteTarget,
    ResolvedMemoryPolicy,
    ResolvedMemoryPolicySource,
)
from domain.rag.schemas.embedding_job import EmbeddingStatus
from domain.rag.schemas.rag import RagPreparedDocument


def _observe_context() -> MagicMock:
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=None)
    return cm


@pytest.fixture
def tracer() -> MagicMock:
    t = MagicMock()
    t.observe = MagicMock(return_value=_observe_context())
    return t


@pytest.fixture
def execution_repository() -> MagicMock:
    return MagicMock()


class TestMemoryWriteServiceVectorCap:
    @pytest.mark.asyncio
    async def test_vector_branch_skips_ingest_when_cap_reached(
        self,
        tracer: MagicMock,
        execution_repository: MagicMock,
    ) -> None:
        tenant_id = uuid4()
        rag_config_id = uuid4()
        policy = ResolvedMemoryPolicy(
            source=ResolvedMemoryPolicySource.TENANT_ACTIVE,
            tenant_id=tenant_id,
            policy_version_id=uuid4(),
            definition=MemoryPolicyDefinition(
                allowed_sources=[MemoryPolicySource.ADMIN_SEED],
                allowed_schemas=[
                    AllowedSchema(
                        schema_id="test_schema",
                        write_targets=[MemoryWriteTarget.USER_MEMORY_VECTOR],
                    )
                ],
            ),
        )
        policy_service = MagicMock()
        policy_service.enforce_write = AsyncMock(return_value=(policy, None))

        rag_runtime = MagicMock()
        rag_runtime.resolve_user_memory_vector_document_cap = AsyncMock(
            return_value={
                "effective_cap": 3,
                "app_max_user_memory_documents": 10_000,
                "tenant_max_documents_per_user": 3,
                "binding": "rag_policy",
                "reason_code": "rag_ingest_quota_user_documents",
            }
        )
        rag_runtime.count_user_memory_documents_for_rag_config = AsyncMock(return_value=3)
        rag_runtime.prepare_document_for_embedding = AsyncMock()

        svc = MemoryWriteService(
            policy_service=policy_service,
            rag_runtime_service=rag_runtime,
            repository=execution_repository,
            tracer=tracer,
            embedding_job_queue=None,
        )
        await svc.write_memory_item(
            tenant_id=tenant_id,
            user_id="u1",
            item={
                "schema_id": "test_schema",
                "schema_version": 1,
                "source": MemoryPolicySource.ADMIN_SEED.value,
                "rag_config_id": str(rag_config_id),
                "data": {"note": "x"},
            },
        )

        rag_runtime.prepare_document_for_embedding.assert_not_called()
        cap_calls = [
            c
            for c in tracer.observe.call_args_list
            if c.kwargs.get("name") == "domain.memory.write.cap_reached"
        ]
        assert len(cap_calls) == 1
        payload = cap_calls[0].kwargs["input"]
        assert payload["reason_code"] == "rag_ingest_quota_user_documents"
        assert payload["effective_cap"] == 3
        assert payload["current_count"] == 3
        assert payload["rag_config_id"] == str(rag_config_id)

    @pytest.mark.asyncio
    async def test_vector_branch_ingests_when_below_cap(
        self,
        tracer: MagicMock,
        execution_repository: MagicMock,
    ) -> None:
        tenant_id = uuid4()
        rag_config_id = uuid4()
        doc_id = uuid4()
        policy = ResolvedMemoryPolicy(
            source=ResolvedMemoryPolicySource.TENANT_ACTIVE,
            tenant_id=tenant_id,
            policy_version_id=uuid4(),
            definition=MemoryPolicyDefinition(
                allowed_sources=[MemoryPolicySource.ADMIN_SEED],
                allowed_schemas=[
                    AllowedSchema(
                        schema_id="test_schema",
                        write_targets=[MemoryWriteTarget.USER_MEMORY_VECTOR],
                    )
                ],
            ),
        )
        policy_service = MagicMock()
        policy_service.enforce_write = AsyncMock(return_value=(policy, None))

        rag_runtime = MagicMock()
        rag_runtime.resolve_user_memory_vector_document_cap = AsyncMock(
            return_value={
                "effective_cap": 100,
                "app_max_user_memory_documents": 100,
                "tenant_max_documents_per_user": None,
                "binding": "app",
                "reason_code": "app_max_user_memory_documents",
            }
        )
        rag_runtime.count_user_memory_documents_for_rag_config = AsyncMock(return_value=2)
        rag_runtime.prepare_document_for_embedding = AsyncMock(
            return_value=RagPreparedDocument(
                id=doc_id,
                content_hash="h",
                embedding_status=EmbeddingStatus.COMPLETED,
            )
        )

        svc = MemoryWriteService(
            policy_service=policy_service,
            rag_runtime_service=rag_runtime,
            repository=execution_repository,
            tracer=tracer,
            embedding_job_queue=None,
        )
        await svc.write_memory_item(
            tenant_id=tenant_id,
            user_id="u1",
            item={
                "schema_id": "test_schema",
                "schema_version": 1,
                "source": MemoryPolicySource.ADMIN_SEED.value,
                "rag_config_id": str(rag_config_id),
                "data": {"note": "y"},
            },
        )

        rag_runtime.prepare_document_for_embedding.assert_awaited_once()
        cap_calls = [
            c
            for c in tracer.observe.call_args_list
            if c.kwargs.get("name") == "domain.memory.write.cap_reached"
        ]
        assert cap_calls == []
