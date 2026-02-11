from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from uuid import UUID, uuid4

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.execution.schemas.trace import TraceContext
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfigOptions, RagDocumentCreate
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import get_db
from infra.database import DatabaseConnection, async_session, engine
from infra.database.models.rag.rag_config import RagConfig
from infra.database.models.rag.vector_store import VectorStore
from settings import OPENAI_API_KEY

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    VECTOR_STORE_DEMO_ID,
)


class _SeedObservationHandle:
    def update(self, **kwargs) -> None:
        return None

    def success(self, *, output, metadata=None, **kwargs) -> None:
        return None

    def error(
        self,
        *,
        error_type: str,
        error_message: str,
        output=None,
        metadata=None,
        level: str = "ERROR",
        status_message: str | None = None,
        **kwargs,
    ) -> None:
        return None


class _SeedTracer:
    def start_flow_trace(
        self,
        *,
        flow_run_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: str | None,
        external_request_id: str | None = None,
        trace_id: UUID | None = None,
        interaction_id: UUID | None = None,
        correlation_id: UUID | None = None,
        channel: str | None = None,
        external_message_id: str | None = None,
        graph_snapshot_id: UUID | None = None,
        execution_plan_hash: str | None = None,
        flow_name: str | None = None,
    ) -> TraceContext:
        return TraceContext(
            trace_id=trace_id or uuid4(),
            flow_run_id=flow_run_id or uuid4(),
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            root_observation_id=None,
            flow_name=flow_name,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            interaction_id=interaction_id,
            correlation_id=correlation_id,
            channel=channel,
            external_message_id=external_message_id,
            graph_snapshot_id=graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
        )

    @contextlib.contextmanager
    def flow(self, *, trace: TraceContext, input, name: str | None = None):
        handle = _SeedObservationHandle()
        yield handle

    @contextlib.contextmanager
    def observe(
        self,
        *,
        as_type: str,
        name: str,
        input,
        metadata=None,
        trace_context=None,
        **kwargs,
    ):
        handle = _SeedObservationHandle()
        yield handle

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


async def seed_rag() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(VectorStore).where(
                VectorStore.vector_store_id == VECTOR_STORE_DEMO_ID
            )
        )
        existing_store = result.scalar_one_or_none()

        if existing_store is None:
            vector_store = VectorStore(
                vector_store_id=VECTOR_STORE_DEMO_ID,
                name="Demo Vector Store",
            )
            session.add(vector_store)
            await session.commit()

        result = await session.execute(
            select(RagConfig).where(RagConfig.rag_config_id == RAG_CONFIG_DEMO_ID)
        )
        existing_config = result.scalar_one_or_none()

        if existing_config is None:
            options = RagConfigOptions().model_dump(mode="json")
            rag_config = RagConfig(
                rag_config_id=RAG_CONFIG_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                vector_store_id=VECTOR_STORE_DEMO_ID,
                status="PUBLISHED",
                version_major=1,
                version_minor=0,
                version_patch=0,
                options=options,
            )
            session.add(rag_config)
            await session.commit()
        else:
            options = existing_config.options
            if not options:
                options = RagConfigOptions().model_dump(mode="json")
                existing_config.options = options
            if existing_config.status != "PUBLISHED":
                existing_config.status = "PUBLISHED"
            await session.commit()

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for RAG seed ingestion")

    database_connection = DatabaseConnection(engine=engine, sessionmaker=async_session)
    rag_repository = RagRepository(database_connection)
    tracer = _SeedTracer()
    embedding_adapter = OpenAIEmbeddingAdapter(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",
        dimension=1536,
        tracer=tracer,
    )
    rag_runtime_service = RagRuntimeService(
        repository=rag_repository,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )
    documents = [
        RagDocumentCreate(
            source="demo",
            doc_type="policy",
            content="The financial assistant can track expenses, budgets, and categories.",
            version="1",
            metadata={"topic": "assistant"},
        ),
        RagDocumentCreate(
            source="demo",
            doc_type="currency",
            content="Supported currencies include BRL and USD for expense tracking.",
            version="1",
            metadata={"topic": "currency"},
        ),
    ]
    for document in documents:
        await rag_runtime_service.ingest_document(
            tenant_id=TENANT_DEMO_ID,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            document=document,
        )
