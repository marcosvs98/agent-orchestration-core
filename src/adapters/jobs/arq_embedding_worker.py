from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

import settings
from adapters.cache.redis_adapter import RedisAdapter
from adapters.rag.embedding_adapter import OpenAIEmbeddingAdapter
from adapters.observability.otel_bootstrap import bootstrap_telemetry, shutdown_telemetry
from adapters.observability.otel_runtime_tracer import OtelRuntimeTracer
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.execution.schemas.events import ExecutionEventType
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.embedding_job import EmbeddingJobPayload
from domain.rag.services.embedding_adapter_factory import EmbeddingProviderFactory
from domain.rag.services.embedding_executor import EmbeddingExecutor
from domain.rag.services.embedding_provider_selector import EmbeddingProviderSelector
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import DatabaseConnection, async_session, engine


async def process_embedding_job(ctx: dict[str, Any], payload_data: dict[str, object]) -> None:
    payload = EmbeddingJobPayload.model_validate(payload_data)
    execution_repository: ExecutionRepository = ctx["execution_repository"]
    rag_repository: RagRepository = ctx["rag_repository"]
    rag_runtime_service: RagRuntimeService = ctx["rag_runtime_service"]
    tracer = ctx["tracer"]
    existing_document = await rag_repository.get_document_by_id(document_id=payload.document_id)
    attempt = (int(existing_document.embedding_attempts) + 1) if existing_document else 1
    with tracer.observe(
        as_type="event",
        name="domain.rag.embedding.started",
        input={
            "document_id": str(payload.document_id),
            "rag_config_id": str(payload.rag_config_id),
            "attempt": attempt,
        },
        metadata={"event_type": ExecutionEventType.MemoryEmbeddingStarted.value},
    ) as event_span:
        event_payload: dict = {
            "document_id": str(payload.document_id),
            "rag_config_id": str(payload.rag_config_id),
            "flow_run_id": str(payload.flow_run_id) if payload.flow_run_id else None,
            "attempt": attempt,
        }
        await _append_execution_event(
            repository=execution_repository,
            payload=payload,
            event_type=ExecutionEventType.MemoryEmbeddingStarted,
            event_payload=event_payload,
        )
        if event_span:
            event_span.update(output=event_payload)
    try:
        await rag_runtime_service.embed_document_by_id(
            tenant_id=payload.tenant_id,
            rag_config_id=payload.rag_config_id,
            document_id=payload.document_id,
        )
        with tracer.observe(
            as_type="event",
            name="domain.rag.embedding.completed",
            input={
                "document_id": str(payload.document_id),
                "rag_config_id": str(payload.rag_config_id),
            },
            metadata={"event_type": ExecutionEventType.MemoryEmbeddingCompleted.value},
        ) as event_span:
            embedded_payload = {
                "scope": "USER_MEMORY",
                "target": "USER_MEMORY_VECTOR",
                "schema_id": payload.schema_id,
                "schema_version": payload.schema_version,
                "source": "INFERRED_LLM",
                "policy_version_id": str(payload.policy_version_id)
                if payload.policy_version_id
                else None,
                "rag_config_id": str(payload.rag_config_id),
                "document_id": str(payload.document_id),
            }
            await _append_execution_event(
                repository=execution_repository,
                payload=payload,
                event_type=ExecutionEventType.MemoryEmbedded,
                event_payload=embedded_payload,
            )
            await _append_execution_event(
                repository=execution_repository,
                payload=payload,
                event_type=ExecutionEventType.MemoryEmbeddingCompleted,
                event_payload={
                    "document_id": str(payload.document_id),
                    "rag_config_id": str(payload.rag_config_id),
                    "flow_run_id": str(payload.flow_run_id) if payload.flow_run_id else None,
                },
            )
            if event_span:
                event_span.update(output=embedded_payload)
    except Exception as exc:
        document = await rag_repository.get_document_by_id(document_id=payload.document_id)
        attempt = int(document.embedding_attempts) if document else attempt
        error_code = exc.__class__.__name__
        with tracer.observe(
            as_type="event",
            name="domain.rag.embedding.failed",
            input={
                "document_id": str(payload.document_id),
                "rag_config_id": str(payload.rag_config_id),
                "attempt": attempt,
                "error_code": error_code,
            },
            metadata={"event_type": ExecutionEventType.MemoryEmbeddingFailed.value},
        ) as event_span:
            event_payload: dict = {
                "document_id": str(payload.document_id),
                "rag_config_id": str(payload.rag_config_id),
                "flow_run_id": str(payload.flow_run_id) if payload.flow_run_id else None,
                "attempt": attempt,
                "error_code": error_code,
            }
            await _append_execution_event(
                repository=execution_repository,
                payload=payload,
                event_type=ExecutionEventType.MemoryEmbeddingFailed,
                event_payload=event_payload,
            )
            if event_span:
                event_span.update(output=event_payload)
        raise exc from exc


async def startup(ctx: dict[str, Any]) -> None:
    bootstrap_telemetry(component="embedding-worker")
    db = DatabaseConnection(engine=engine, sessionmaker=async_session)
    tracer = OtelRuntimeTracer()
    cache_adapter = RedisAdapter(silent_mode=settings.CACHE_SILENT_MODE)
    execution_repository = ExecutionRepository(db, tracer=tracer, cache_adapter=cache_adapter)
    rag_repository = RagRepository(db, tracer=tracer, cache_adapter=cache_adapter)

    embedding_adapter = OpenAIEmbeddingAdapter(
        api_key=settings.OPENAI_API_KEY,
        model="text-embedding-3-small",
        dimension=settings.EMBEDDING_DIMENSION,
        tracer=tracer,
        cache_adapter=cache_adapter,
    )
    embedding_selector = EmbeddingProviderSelector(tracer=tracer)
    embedding_factory = EmbeddingProviderFactory(
        tracer=tracer,
        openai_provider=embedding_adapter,
    )
    embedding_executor = EmbeddingExecutor(
        selector=embedding_selector,
        factory=embedding_factory,
        tracer=tracer,
    )

    rag_policy_service = RagPolicyService(repository=execution_repository)
    ai_repository = AIRepository(db, tracer=tracer)
    rag_runtime_service = RagRuntimeService(
        repository=rag_repository,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
        rag_policy_service=rag_policy_service,
        ai_repository=ai_repository,
        embedding_executor=embedding_executor,
    )
    ctx["tracer"] = tracer
    ctx["execution_repository"] = execution_repository
    ctx["rag_repository"] = rag_repository
    ctx["rag_runtime_service"] = rag_runtime_service


async def _append_execution_event(
    *,
    repository: ExecutionRepository,
    payload: EmbeddingJobPayload,
    event_type: ExecutionEventType,
    event_payload: dict[str, object],
) -> None:
    if payload.session_id is None or payload.flow_run_id is None or payload.correlation_id is None:
        return
    await repository.append_execution_event(
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        session_id=payload.session_id,
        flow_run_id=payload.flow_run_id,
        event_type=event_type.value,
        payload=event_payload,
        correlation_id=payload.correlation_id,
        causation_id=None,
        schema_version=1,
        node_id=None,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    shutdown_telemetry()


class WorkerSettings:
    functions = [process_embedding_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        database=settings.REDIS_DB,
        ssl=settings.REDIS_SSL,
    )
    max_tries = settings.EMBEDDING_QUEUE_MAX_ATTEMPTS
