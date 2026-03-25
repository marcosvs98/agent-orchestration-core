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
    NodeExecutionStatus,
    ToolIntentFilter,
)
from domain.prompts.schemas.prompt import NodeType
from domain.rag.schemas.rag import RagDocumentCreate
from domain.tools.schemas.tools import AvailableTool
from resources.scripts.examples.nodes.node_validation_context import make_base_context
from resources.scripts.seeds.demo.ids import (
    NODE_INTENT_ID,
    NODE_TOOL_SELECTION_ID,
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    rag = app.rag.rag_runtime_service()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    user_line = "gastei 80 reais no mercado com cartao"
    await rag.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=RagDocumentCreate(
            source="validate_node_intent",
            doc_type="intent_examples",
            content=f"{user_line}\nrun_ref={uuid.uuid4().hex}",
            version="1.0",
            metadata={"intent_type": "command"},
        ),
    )
    await rag.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=RagDocumentCreate(
            source="validate_node_tools",
            doc_type="tool_catalog",
            content=f"{user_line}\nrun_ref={uuid.uuid4().hex}",
            version="1.0",
            metadata={
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "tool_intent": ToolIntentFilter.COMMAND.value,
            },
        ),
    )
    reg = es.runtime.registry
    intent_cls = reg.resolve(NodeType.IntentClassifier.value)
    tool_cls = reg.resolve(NodeType.ToolResolver.value)
    if intent_cls is None or tool_cls is None:
        raise SystemExit("registry_resolve_intent_or_tool_failed")
    intent_node = intent_cls()
    tool_node = tool_cls()
    ictx = make_base_context(
        tenant_id=tenant_id,
        current_node_id=NODE_INTENT_ID,
        user_input=user_line,
    )
    intent_res = await intent_node.execute(
        ictx,
        {"confidence_threshold": 0.35, "top_k": 3},
    )
    if intent_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"intent_detection_failed {intent_res.data!r}")
    tools = [
        AvailableTool(
            name="createExpense",
            tool_id=TOOL_DEMO_ID,
            tool_config_id=TOOL_CONFIG_DEMO_ID,
            operation_id="createExpense",
            method="POST",
            path="/createExpense",
        )
    ]
    merged_state = {**(ictx.state or {}), **(intent_res.next_state or {})}
    tctx = make_base_context(
        tenant_id=tenant_id,
        current_node_id=NODE_TOOL_SELECTION_ID,
        user_input=user_line,
        state=merged_state,
        available_tools=tools,
    )
    tool_res = await tool_node.execute(
        tctx,
        {"confidence_threshold": 0.55, "top_k": 5},
    )
    if tool_res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"tool_selection_failed {tool_res.data!r}")
    print(
        "validate_node_intent_and_tools: ok",
        f"intent_mode={intent_res.data.get('result')}",
        f"tool_result_items={len((tool_res.data.get('result') or []))}",
    )


if __name__ == "__main__":
    asyncio.run(main())
