from __future__ import annotations

import asyncio
import sys
import uuid
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
from domain.execution.services.graph_runtime.types import (
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    NodeExecutionStatus,
)
from domain.prompts.schemas.prompt import NodeType
from resources.scripts.examples.nodes.node_validation_context import (
    llm_node_config,
    make_base_context,
)
from resources.scripts.seeds.demo.ids import NODE_MEMORY_PAYLOAD_SUMMARIZE_ID, TENANT_DEMO_ID


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    reg = es.runtime.registry
    cls = reg.resolve(NodeType.ContextSummarizer.value)
    if cls is None:
        raise SystemExit("registry_resolve_memory_payload_summarize_failed")
    node = cls()
    source_id = f"mem_src_{uuid.uuid4().hex[:12]}"
    large = "x" * 2048
    ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_MEMORY_PAYLOAD_SUMMARIZE_ID,
        user_input="summarize prior node output for memory",
        state={
            NODE_OUTPUTS_BY_NODE_ID_KEY: {
                source_id: {"raw_text": large, "topic": "validation_probe"},
            },
        },
    )
    cfg = {**llm_node_config(), "source_node_id": source_id, "min_payload_bytes_to_run": 1}
    result = await node.execute(ctx, cfg)
    if result.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"memory_payload_summarize_failed status={result.status!s} {result.data!r}")
    if result.data.get("summarize_skipped"):
        raise SystemExit("memory_payload_summarize_should_not_skip_large_payload")
    print(
        "validate_node_memory_payload_summarize: ok",
        f"data_keys={list(result.data.keys())}",
    )


if __name__ == "__main__":
    asyncio.run(main())
