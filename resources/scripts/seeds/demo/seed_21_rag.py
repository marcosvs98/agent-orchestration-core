from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from uuid import UUID, uuid4

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        sys.path.insert(0, str(_repo / "resources" / "scripts"))
        sys.path.insert(0, str(_repo))
        break
else:
    raise RuntimeError("repository root not found")

from sqlalchemy import select

from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.services.embedding_adapter_factory import EmbeddingProviderFactory
from domain.rag.services.embedding_provider_selector import EmbeddingProviderSelector
from adapters.cache.redis_adapter import RedisAdapter
from adapters.rag.embedding_adapter import OpenAIEmbeddingAdapter
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.common.schemas.versioning import VersionStatus
from domain.execution.schemas.trace import TraceContext
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.llm.schemas.llm import LLMProviderType
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import (
    RagConfigOptions,
    RagEmbeddingModelAlias,
    RagEmbeddingOptions,
)
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import get_db
from infra.database import DatabaseConnection, async_session, engine
from infra.database.models.rag.rag_chunking_rule import RagChunkingRule
from infra.database.models.rag.rag_config import RagConfig
from infra.database.models.rag.vector_store import VectorStore
from settings import OPENAI_API_KEY

from seeds.demo.ids import (
    MODEL_CATALOG_EMBEDDING_INDEXING_ID,
    MODEL_CATALOG_EMBEDDING_RETRIEVAL_ID,
    RAG_CHUNKING_RULE_DEMO_ID,
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    VECTOR_STORE_DEMO_ID,
)
from seeds.demo.rag_payloads import demo_assistente_bolso_kb_documents


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


def _demo_rag_options() -> RagConfigOptions:
    large_3072 = RagEmbeddingOptions(
        provider=LLMProviderType.OPENAI,
        model_alias=RagEmbeddingModelAlias.TEXT_EMBEDDING_3_LARGE,
        dimension=3072,
        model_id=MODEL_CATALOG_EMBEDDING_INDEXING_ID,
    )
    small_1536 = RagEmbeddingOptions(
        provider=LLMProviderType.OPENAI,
        model_alias=RagEmbeddingModelAlias.TEXT_EMBEDDING_3_SMALL,
        dimension=1536,
        model_id=MODEL_CATALOG_EMBEDDING_RETRIEVAL_ID,
    )
    return RagConfigOptions(
        indexing_embedding=large_3072,
        embedding=small_1536,
    )


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
                tenant_id=TENANT_DEMO_ID,
                name="Assistente de Bolso - Conhecimento",
                embedding_model="text-embedding-3-large",
                embedding_dimension=3072,
                metric="cosine",
                version=1,
                active=True,
            )
            session.add(vector_store)
            await session.commit()
        else:
            existing_store.embedding_model = "text-embedding-3-large"
            existing_store.embedding_dimension = 3072
            session.add(existing_store)
            await session.commit()

        result = await session.execute(
            select(RagChunkingRule).where(
                RagChunkingRule.rag_chunking_rule_id == RAG_CHUNKING_RULE_DEMO_ID
            )
        )
        existing_rule = result.scalar_one_or_none()
        if existing_rule is None:
            demo_chunking_params = {
                "strategy": "TOKEN_WINDOW",
                "target_tokens": 500,
                "overlap_tokens": 50,
                "max_chunks_per_document": 100,
                "max_document_chars": 100_000,
            }
            session.add(
                RagChunkingRule(
                    rag_chunking_rule_id=RAG_CHUNKING_RULE_DEMO_ID,
                    tenant_id=TENANT_DEMO_ID,
                    name="demo-seed-token-window",
                    status="ACTIVE",
                    strategy="TOKEN_WINDOW",
                    params=demo_chunking_params,
                )
            )
            await session.commit()

        result = await session.execute(
            select(RagConfig).where(RagConfig.rag_config_id == RAG_CONFIG_DEMO_ID)
        )
        existing_config = result.scalar_one_or_none()

        if existing_config is None:
            options = _demo_rag_options().model_dump(mode="json")
            rag_config = RagConfig(
                rag_config_id=RAG_CONFIG_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                vector_store_id=VECTOR_STORE_DEMO_ID,
                chunking_rule_id=RAG_CHUNKING_RULE_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                options=options,
            )
            session.add(rag_config)
            await session.commit()
        else:
            merged = _demo_rag_options()
            if existing_config.options:
                prior = RagConfigOptions.model_validate(existing_config.options)
                merged = merged.model_copy(
                    update={
                        "retrieval": prior.retrieval,
                        "generation_contract": prior.generation_contract,
                    }
                )
            existing_config.options = merged.model_dump(mode="json")
            if existing_config.chunking_rule_id is None:
                existing_config.chunking_rule_id = RAG_CHUNKING_RULE_DEMO_ID
            if existing_config.status != VersionStatus.PUBLISHED.value:
                existing_config.status = VersionStatus.PUBLISHED.value
            await session.commit()

    if not OPENAI_API_KEY:
        raise RuntimeError("`OPENAI_API_KEY` is required for RAG seed ingestion")

    cache_adapter = RedisAdapter()
    database_connection = DatabaseConnection(engine=engine, sessionmaker=async_session)
    tracer = _SeedTracer()
    execution_repository = ExecutionRepository(
        database_connection,
        tracer=tracer,
        cache_adapter=cache_adapter,
    )
    rag_policy_service = RagPolicyService(repository=execution_repository)
    rag_repository = RagRepository(
        database_connection,
        tracer=tracer,
        cache_adapter=cache_adapter,
    )
    embedding_adapter = OpenAIEmbeddingAdapter(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-large",
        dimension=3072,
        tracer=tracer,
        cache_adapter=cache_adapter,
    )
    ai_repository = AIRepository(database_connection, tracer=tracer)

    embedding_provider_selector = EmbeddingProviderSelector(
        tracer=tracer,
    )

    embedding_provider_factory = EmbeddingProviderFactory(
        tracer=tracer,
        embedding_adapter=embedding_adapter,
    )

    embedding_executor = EmbeddingExecutor(
        selector=embedding_provider_selector,
        factory=embedding_provider_factory,
        tracer=tracer,
    )

    rag_runtime_service = RagRuntimeService(
        repository=rag_repository,
        tracer=tracer,
        rag_policy_service=rag_policy_service,
        ai_repository=ai_repository,
        embedding_executor=embedding_executor,
    )
    for document in demo_assistente_bolso_kb_documents():
        await rag_runtime_service.ingest_document(
            tenant_id=TENANT_DEMO_ID,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            document=document,
        )
