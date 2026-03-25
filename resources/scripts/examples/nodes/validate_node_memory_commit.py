from __future__ import annotations

import asyncio
import sys
from pathlib import Path

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        for _p in (_repo, _repo / "src"):
            _s = str(_p)
            if _s not in sys.path:
                sys.path.insert(0, _s)
        break
else:
    raise SystemExit("repository root not found")

from containers import ApplicationContainer
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.prompts.schemas.prompt import NodeType
from resources.scripts.examples.nodes.node_validation_context import make_base_context
from resources.scripts.seeds.demo.ids import (
    NODE_MEMORY_COMMIT_ID,
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
)


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    reg = es.runtime.registry
    cls = reg.resolve(NodeType.MemoryCommitNode.value)
    if cls is None:
        raise SystemExit("registry_resolve_memory_commit_failed")
    node = cls()
    ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_MEMORY_COMMIT_ID,
        user_input="preference note",
    )
    ok = await node.execute(
        ctx,
        {
            "schema_id": "user.preference.v1",
            "schema_version": 1,
            "source": "explicit_user",
            "rag_config_id": str(RAG_CONFIG_DEMO_ID),
            "data": {"preference_key": "currency", "preference_value": "BRL"},
        },
    )
    if ok.status != NodeExecutionStatus.SUCCESS or not ok.memory:
        raise SystemExit(f"memory_commit_success_expected got={ok.status!s} {ok.data!r}")
    bad = await node.execute(ctx, {"rag_config_id": str(RAG_CONFIG_DEMO_ID)})
    if bad.status != NodeExecutionStatus.ERROR:
        raise SystemExit("memory_commit_missing_schema_should_error")
    last = ok.memory[-1]
    print(
        "validate_node_memory_commit: ok",
        f"memory_last_item_keys={list(last.keys())}",
    )


if __name__ == "__main__":
    asyncio.run(main())
