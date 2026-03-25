from __future__ import annotations

import asyncio
import contextlib
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

for project_root in Path(__file__).resolve().parents:
    if (project_root / "pyproject.toml").exists():
        src_path = project_root / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        break
else:
    raise SystemExit("repository root not found")

from adapters.cache.redis_adapter import RedisAdapter
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.common.schemas.versioning import VersionStatus
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.trace import TraceContext
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfigOptions, RagDocumentCreate
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import DatabaseConnection, async_session, engine, get_db
from infra.database.models.rag.rag_chunking_rule import RagChunkingRule
from infra.database.models.rag.rag_config import RagConfig
from settings import EMBEDDING_DIMENSION, OPENAI_API_KEY

from resources.scripts.seeds.demo.ids import TENANT_DEMO_ID, VECTOR_STORE_DEMO_ID
from resources.scripts.seeds.demo.rag_payloads import demo_long_chunking_sample_text


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


def _mean_chunk_chars(chunks: list) -> float:
    if not chunks:
        return 0.0
    return float(statistics.mean(len(c.content) for c in chunks))


def _median_chunk_chars(chunks: list) -> float:
    if not chunks:
        return 0.0
    return float(statistics.median(len(c.content) for c in chunks))


def _build_pages_from_text(text: str, page_chars: int = 1200) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + page_chars, len(text))
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    return out


def _strategy_score(
    *,
    chunks: int,
    mean_chars: float,
    capped: bool,
) -> float:
    chunk_target = 220.0
    mean_target = 260.0
    chunk_score = max(0.0, 55.0 - (abs(chunks - chunk_target) * 0.22))
    mean_score = max(0.0, 45.0 - (abs(mean_chars - mean_target) * 0.10))
    cap_penalty = 30.0 if capped else 0.0
    return chunk_score + mean_score - cap_penalty


@dataclass(frozen=True)
class _StrategySpec:
    label: str
    strategy: str
    params: dict[str, object]


@dataclass(frozen=True)
class _ModelSpec:
    label: str
    model: str
    dimension: int


async def main() -> None:
    if not OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is required for chunking comparison")
    run_tag = uuid4().hex[:12]
    ver_major = int(time.time() % 1_000_000_000)
    specs = [
        _StrategySpec(
            label="token_window",
            strategy="TOKEN_WINDOW",
            params={
                "strategy": "TOKEN_WINDOW",
                "target_tokens": 220,
                "overlap_tokens": 35,
                "max_chunks_per_document": 1000,
                "max_document_chars": 500_000,
            },
        ),
        _StrategySpec(
            label="recursive_character",
            strategy="RECURSIVE_CHARACTER",
            params={
                "strategy": "RECURSIVE_CHARACTER",
                "chunk_size": 1300,
                "chunk_overlap": 200,
                "max_chunks_per_document": 1000,
                "max_document_chars": 500_000,
                "separators": ["\n\n", "\n", ". ", " ", ""],
            },
        ),
        _StrategySpec(
            label="semantic",
            strategy="SEMANTIC",
            params={
                "strategy": "SEMANTIC",
                "target_tokens": 180,
                "overlap_tokens": 25,
                "max_chunks_per_document": 1000,
                "max_document_chars": 500_000,
            },
        ),
        _StrategySpec(
            label="per_page",
            strategy="PER_PAGE",
            params={
                "strategy": "PER_PAGE",
                "max_chunks_per_document": 1000,
                "max_document_chars": 500_000,
                "pages": [],
            },
        ),
    ]
    models = [
        _ModelSpec(
            label="text_embedding_3_small",
            model="text-embedding-3-small",
            dimension=EMBEDDING_DIMENSION,
        ),
        _ModelSpec(
            label="text_embedding_3_large",
            model="text-embedding-3-large",
            dimension=EMBEDDING_DIMENSION,
        ),
    ]

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
    body = demo_long_chunking_sample_text(run_tag=run_tag)
    pages = _build_pages_from_text(body, page_chars=1200)
    results: list[dict[str, object]] = []
    for model_idx, model_spec in enumerate(models):
        rule_ids = [uuid4() for _ in specs]
        cfg_ids = [uuid4() for _ in specs]
        async with get_db() as session:
            session.add_all([
                RagChunkingRule(
                    rag_chunking_rule_id=rule_ids[idx],
                    tenant_id=TENANT_DEMO_ID,
                    name=f"validate-chunk-{model_spec.label}-{spec.label}-{run_tag}",
                    status="ACTIVE",
                    strategy=spec.strategy,
                    params=spec.params,
                )
                for idx, spec in enumerate(specs)
            ])
            for idx, _spec in enumerate(specs):
                options = RagConfigOptions().model_dump(mode="json")
                options["embedding"]["model_alias"] = model_spec.model
                options["embedding"]["dimension"] = model_spec.dimension
                session.add(
                    RagConfig(
                        rag_config_id=cfg_ids[idx],
                        tenant_id=TENANT_DEMO_ID,
                        vector_store_id=VECTOR_STORE_DEMO_ID,
                        chunking_rule_id=rule_ids[idx],
                        status=VersionStatus.PUBLISHED.value,
                        version_major=ver_major + model_idx,
                        version_minor=idx,
                        version_patch=0,
                        options=options,
                    )
                )
            await session.commit()
        embedding_adapter = OpenAIEmbeddingAdapter(
            api_key=OPENAI_API_KEY,
            model=model_spec.model,
            dimension=model_spec.dimension,
            tracer=tracer,
            cache_adapter=cache_adapter,
        )
        rag_runtime_service = RagRuntimeService(
            repository=rag_repository,
            embedding_adapter=embedding_adapter,
            tracer=tracer,
            rag_policy_service=rag_policy_service,
        )
        for idx, spec in enumerate(specs):
            profile = f"{model_spec.label}_{spec.label}"
            try:
                doc = RagDocumentCreate(
                    source="validate_rag_chunking_strategies",
                    doc_type="chunking_probe",
                    content=f"{body}\nchunking_profile={profile}",
                    version="1.0",
                    metadata={"run_tag": run_tag, "profile": profile},
                    pages=pages if spec.strategy == "PER_PAGE" else None,
                )
                out = await rag_runtime_service.ingest_document(
                    tenant_id=TENANT_DEMO_ID,
                    rag_config_id=cfg_ids[idx],
                    document=doc,
                )
                chunks = await rag_runtime_service.list_chunks(
                    document_id=out.id, limit=5000
                )
                mean_chars = _mean_chunk_chars(chunks)
                median_chars = _median_chunk_chars(chunks)
                max_chunks = int(spec.params["max_chunks_per_document"])
                capped = len(chunks) >= max_chunks
                score = _strategy_score(
                    chunks=len(chunks), mean_chars=mean_chars, capped=capped
                )
                token_volume_est = (len(chunks) * mean_chars) / 4.0
                efficiency_score = max(0.0, 100.0 - (token_volume_est / 120.0))
                balanced_score = (score * 0.7) + (efficiency_score * 0.3)
                results.append(
                    {
                        "model": model_spec.model,
                        "label": spec.label,
                        "strategy": spec.strategy,
                        "chunks": len(chunks),
                        "mean_chars": mean_chars,
                        "median_chars": median_chars,
                        "token_volume_est": token_volume_est,
                        "capped": capped,
                        "quality_score": score,
                        "efficiency_score": efficiency_score,
                        "balanced_score": balanced_score,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "model": model_spec.model,
                        "label": spec.label,
                        "strategy": spec.strategy,
                        "failed": True,
                        "error": str(exc),
                    }
                )
    ok_results = [x for x in results if not x.get("failed")]
    if not ok_results:
        raise SystemExit("no successful model/strategy combination")
    ranking = sorted(ok_results, key=lambda x: float(x["balanced_score"]), reverse=True)
    best = ranking[0]
    print(
        "rag_chunking_model_strategy_comparison_ok",
        f"run_tag={run_tag}",
        f"models_compared={len(models)}",
        f"strategies_compared={len(specs)}",
        f"combinations_successful={len(ok_results)}",
        sep="\n",
    )
    for item in results:
        if item.get("failed"):
            print(
                f"model={item['model']} strategy={item['strategy']} "
                f"label={item['label']} failed=true error={item['error']}"
            )
    for item in ranking:
        print(
            f"model={item['model']} strategy={item['strategy']} label={item['label']} "
            f"chunks={item['chunks']} mean_chars={float(item['mean_chars']):.1f} "
            f"median_chars={float(item['median_chars']):.1f} "
            f"token_volume_est={float(item['token_volume_est']):.1f} "
            f"capped={item['capped']} quality={float(item['quality_score']):.2f} "
            f"efficiency={float(item['efficiency_score']):.2f} "
            f"balanced={float(item['balanced_score']):.2f}"
        )
    print(
        "best_model_strategy",
        f"model={best['model']}",
        f"strategy={best['strategy']}",
        f"label={best['label']}",
        f"balanced={float(best['balanced_score']):.2f}",
        sep="\n",
    )

    if not all(int(item["chunks"]) >= 1 for item in ok_results):
        raise SystemExit("all successful combinations must generate at least one chunk")


if __name__ == "__main__":
    asyncio.run(main())
