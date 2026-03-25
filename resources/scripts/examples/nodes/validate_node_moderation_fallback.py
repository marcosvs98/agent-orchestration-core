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
from resources.scripts.examples.nodes.node_validation_context import (
    llm_node_config,
    make_base_context,
)
from resources.scripts.seeds.demo.ids import (
    NODE_FALLBACK_SLA_ID,
    NODE_INPUT_MODERATION_ID,
    TENANT_DEMO_ID,
)


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    reg = es.runtime.registry
    m_cls = reg.resolve(NodeType.ContentModeration.value)
    f_cls = reg.resolve(NodeType.HumanFallback.value)
    if m_cls is None or f_cls is None:
        raise SystemExit("registry_resolve_moderation_or_fallback_failed")
    m_node = m_cls()
    f_node = f_cls()
    m_ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_INPUT_MODERATION_ID,
        user_input="hello support I need help with billing",
    )
    m_res = await m_node.execute(m_ctx, {})
    if m_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"input_moderation_failed {m_res.data!r}")
    f_ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_FALLBACK_SLA_ID,
        user_input="please escalate my case to a human agent",
        metadata_extra={
            "fallback_reason": "LOW_CONFIDENCE",
            "current_node_type": "ToolResolver",
        },
    )
    f_res = await f_node.execute(f_ctx, llm_node_config())
    if f_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"fallback_node_failed {f_res.data!r}")
    print(
        "validate_node_moderation_fallback: ok",
        f"moderation_flagged={m_res.data.get('flagged')}",
        f"fallback_data_keys={list((f_res.data or {}).keys())}",
    )


if __name__ == "__main__":
    asyncio.run(main())
