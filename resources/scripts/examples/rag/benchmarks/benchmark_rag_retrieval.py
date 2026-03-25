from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from uuid import UUID

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
from domain.rag.schemas.rag import RagDocumentCreate
from resources.scripts.seeds.demo.ids import RAG_CONFIG_DEMO_ID, TENANT_DEMO_ID

PROFILE = {
    "k": 5,
    "self_test": True,
    "jsonl": Path(__file__).with_name("demo_golden.jsonl"),
}


def _hit_at_k(
    *,
    ranked_document_ids: list[UUID],
    gold: list[UUID],
    k: int,
) -> tuple[bool, bool]:
    top = ranked_document_ids[:k]
    hit_k = any(g in top for g in gold)
    hit_1 = bool(top) and top[0] in set(gold)
    return hit_k, hit_1


async def run_self_test(*, k: int) -> None:
    app = ApplicationContainer()
    rrs = app.rag.rag_runtime_service()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    token = uuid.uuid4().hex
    doc = RagDocumentCreate(
        source="benchmark_self_test",
        doc_type="benchmark_probe",
        content=f"Retrieval self-test marker {token} for embedding alignment.",
        version="1",
        metadata={"token": token},
    )
    ingested = await rrs.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=doc,
    )
    ctx = await rrs.get_context(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        user_input=f"self-test marker {token}",
        top_k_override=max(k, 5),
    )
    ranked = [it.document_id for it in (ctx.context_items or [])]
    gold = [ingested.id]
    hit_k, hit_1 = _hit_at_k(ranked_document_ids=ranked, gold=gold, k=k)
    print(
        json.dumps(
            {
                "mode": "self_test",
                "k": k,
                "document_id": str(ingested.id),
                "recall_at_k": hit_k,
                "hit_at_1": hit_1,
                "ranked_top": [str(x) for x in ranked[:5]],
            }
        )
    )
    if not hit_k:
        raise SystemExit("self_test failed recall_at_k")


async def run_jsonl(*, path: Path, k: int) -> None:
    app = ApplicationContainer()
    rrs = app.rag.rag_runtime_service()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    total = 0
    hits_k = 0
    hits_1 = 0
    skipped = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            query = row["query"]
            gold_raw = row.get("gold_document_ids") or []
            gold = [UUID(g) for g in gold_raw]
            if not gold:
                skipped += 1
                continue
            ctx = await rrs.get_context(
                tenant_id=tenant_id,
                rag_config_id=rag_config_id,
                user_input=str(query),
                top_k_override=k,
            )
            ranked = [it.document_id for it in (ctx.context_items or [])]
            hit_k, hit_1 = _hit_at_k(ranked_document_ids=ranked, gold=gold, k=k)
            total += 1
            hits_k += int(hit_k)
            hits_1 += int(hit_1)
    recall = (hits_k / total) if total else 0.0
    hit1_rate = (hits_1 / total) if total else 0.0
    print(
        json.dumps(
            {
                "jsonl": str(path),
                "k": k,
                "evaluated": total,
                "skipped_empty_gold": skipped,
                "recall_at_k": recall,
                "hit_at_1": hit1_rate,
            }
        )
    )


async def main() -> None:
    profile_out = dict(PROFILE)
    jl = profile_out.get("jsonl")
    profile_out["jsonl"] = str(jl) if jl is not None else None
    print(json.dumps({"profile": profile_out}))
    k = int(PROFILE["k"])
    if PROFILE.get("self_test"):
        await run_self_test(k=k)
        return
    jl = PROFILE.get("jsonl")
    if jl is None:
        raise SystemExit("profile: set self_test True or jsonl path")
    await run_jsonl(path=Path(jl), k=k)


if __name__ == "__main__":
    asyncio.run(main())
