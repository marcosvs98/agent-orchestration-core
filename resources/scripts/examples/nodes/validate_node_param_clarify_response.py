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
from domain.tools.schemas.tools import AvailableTool
from resources.scripts.examples.nodes.node_validation_context import (
    llm_node_config,
    make_base_context,
)
from resources.scripts.seeds.demo.ids import (
    NODE_CLARIFICATION_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    reg = es.runtime.registry
    p_cls = reg.resolve(NodeType.ToolInputFiller.value)
    c_cls = reg.resolve(NodeType.QueryClarifier.value)
    r_cls = reg.resolve(NodeType.ResponseBuilder.value)
    if p_cls is None or c_cls is None or r_cls is None:
        raise SystemExit("registry_resolve_param_clarify_response_failed")
    tool = AvailableTool(
        name="createExpense",
        tool_id=TOOL_DEMO_ID,
        tool_config_id=TOOL_CONFIG_DEMO_ID,
        operation_id="createExpense",
        method="POST",
        path="/createExpense",
    )
    base_state = {
        NodeType.IntentClassifier.value: {
            "result": [{"intent_type": "command", "confidence": 0.9, "priority": 1}],
            "overall_confidence": 0.9,
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                    },
                    "confidence": 0.9,
                }
            ]
        },
    }
    p_node = p_cls()
    p_ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_SLOT_ID,
        user_input="spent 80 BRL at the store using card",
        state=dict(base_state),
        available_tools=[tool],
    )
    p_res = await p_node.execute(p_ctx, llm_node_config())
    if p_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"param_extraction_failed {p_res.data!r}")
    slot_state = {**base_state, **(p_res.next_state or {})}
    c_node = c_cls()
    c_ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_CLARIFICATION_ID,
        user_input="need more detail on the expense category",
        state=slot_state,
        available_tools=[tool],
    )
    c_res = await c_node.execute(c_ctx, llm_node_config())
    if c_res.status != NodeExecutionStatus.NEEDS_INPUT:
        raise SystemExit(
            f"clarification_expected_needs_input got={c_res.status!s} {c_res.data!r}"
        )
    r_node = r_cls()
    r_ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_RESPONSE_ID,
        user_input="thanks summarize what we captured",
        state=slot_state,
        available_tools=[tool],
    )
    r_res = await r_node.execute(r_ctx, llm_node_config())
    if r_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"response_composer_failed {r_res.data!r}")
    print(
        "validate_node_param_clarify_response: ok",
        f"param_keys={list((p_res.data or {}).keys())}",
        f"clarify_keys={list((c_res.data or {}).keys())}",
        f"response_keys={list((r_res.data or {}).keys())}",
    )


if __name__ == "__main__":
    asyncio.run(main())
