from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

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

from containers import ApplicationContainer
from domain.rag.schemas.rag import RagCorpusKind, RagDocumentCreate
from domain.tools.services.tool_catalog_retriever import (
    TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP,
)
from resources.scripts.seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)

USER_INPUT = "Gastei 80 reais em pizza ontem"
INGEST_PROBE = True
TOP_K = 8
SIMILARITY_CAP = TOOL_CATALOG_SIMILARITY_THRESHOLD_CAP
EXPECTED_OPERATION_ID = "createexpense"
REQUIRE_IN_TOP_N = 0


def _norm_tool_id(meta: object) -> str:
    if not isinstance(meta, dict):
        return ""
    op = meta.get("operation_id")
    name = meta.get("tool_name")
    raw = op if op else name
    if raw is None:
        return ""
    return str(raw).strip().lower()


async def main() -> None:
    app = ApplicationContainer()
    rag = app.rag.rag_runtime_service()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID

    if INGEST_PROBE:
        run_ref = uuid.uuid4().hex
        await rag.ingest_document(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            document=RagDocumentCreate(
                source="tool_catalog",
                doc_type="tool_catalog",
                content=f"{USER_INPUT}\nrun_ref={run_ref}",
                version="1.0",
                metadata={
                    "category": RagCorpusKind.TOOL_CATALOG.value,
                    "tool_id": str(TOOL_DEMO_ID),
                    "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                    "tool_name": "createExpense",
                    "operation_id": "createExpense",
                    "method": "POST",
                    "path": "/createExpense",
                },
            ),
        )

    filters_override: dict[str, object] = {
        "source": "tool_catalog",
        "doc_type": "tool_catalog",
        "category": RagCorpusKind.TOOL_CATALOG.value,
    }
    t0 = time.monotonic()
    ctx = await rag.get_context(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        user_id=None,
        user_input=USER_INPUT,
        filters_override=filters_override,
        top_k_override=max(1, min(TOP_K, 50)),
        similarity_threshold_cap=SIMILARITY_CAP,
    )
    elapsed_ms = (time.monotonic() - t0) * 1000.0

    rows: list[dict[str, object]] = []
    for it in ctx.context_items:
        meta = it.metadata if isinstance(it.metadata, dict) else {}
        rows.append(
            {
                "score": it.score,
                "operation_id": meta.get("operation_id"),
                "tool_name": meta.get("tool_name"),
                "chunk_preview": (it.content or "")[:160],
            }
        )

    payload = {
        "eligible": ctx.eligible,
        "reason": str(ctx.reason),
        "latency_ms": round(elapsed_ms, 2),
        "item_count": len(ctx.context_items),
        "items": rows,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not ctx.eligible or not ctx.context_items:
        raise SystemExit(
            "no_hits: adjust SIMILARITY_CAP or TOP_K, run seeds, or set INGEST_PROBE True"
        )

    ranked = sorted(ctx.context_items, key=lambda x: x.score, reverse=True)
    limit = (
        len(ranked)
        if REQUIRE_IN_TOP_N <= 0
        else min(REQUIRE_IN_TOP_N, len(ranked))
    )
    window = ranked[:limit] if limit else ranked
    found = any(_norm_tool_id(it.metadata) == EXPECTED_OPERATION_ID for it in window)
    if not found:
        got = [_norm_tool_id(it.metadata) for it in window]
        raise SystemExit(
            f"expected_tool_not_found want={EXPECTED_OPERATION_ID!r} "
            f"in_top_{limit or len(ranked)} got={got!r}"
        )


if __name__ == "__main__":
    asyncio.run(main())
