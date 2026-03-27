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
from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.services.embedding_adapter_factory import EmbeddingProviderFactory
from domain.rag.services.embedding_provider_selector import EmbeddingProviderSelector
from adapters.cache.redis_adapter import RedisAdapter
from adapters.rag.embedding_adapter import OpenAIEmbeddingAdapter
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.trace import TraceContext
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import DatabaseConnection, async_session, engine
from settings import OPENAI_API_KEY

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)
from seeds.demo.rag_payloads import demo_tool_catalog_seed_documents


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


async def seed_tool_catalog_rag() -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("`OPENAI_API_KEY` is required for tool catalog RAG seed")

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
        embedding_executor=embedding_executor
    )

    for document in demo_tool_catalog_seed_documents(
        tool_id=TOOL_DEMO_ID,
        tool_config_id=TOOL_CONFIG_DEMO_ID,
    ):
        await rag_runtime_service.ingest_document(
            tenant_id=TENANT_DEMO_ID,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            document=document,
        )
