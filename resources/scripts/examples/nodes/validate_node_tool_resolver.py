from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from uuid import UUID

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
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import FlowRunInput
from domain.execution.services.graph_runtime.types import (
    NodeExecutionStatus,
    ToolIntentFilter,
)
from domain.prompts.schemas.prompt import NodeType
from domain.rag.schemas.rag import RagDocumentCreate
from resources.scripts.examples.nodes.node_validation_context import (
    llm_node_config,
    make_base_context,
)
from resources.scripts.seeds.demo.ids import (
    FLOW_VERSION_V1_ID,
    NODE_TOOL_SELECTION_ID,
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


async def main() -> None:
    user_line = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "gastei 80 reais no mercado com cartão"
    )
    app = ApplicationContainer()
    es = app.execution.execution_service()
    rag = app.rag.rag_runtime_service()
    repository: ExecutionRepository = app.execution.execution_repository()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    correlation_id = uuid.uuid4()
    session_id = uuid.uuid4()
    probe_user_id = "node_validate_tool_resolver"
    flow_run_id = await repository.create_flow_run(
        session_id=UUID("4a77dbf0-af03-4bee-9382-17aac00da303"),
        flow_version_id=FLOW_VERSION_V1_ID,
        correlation_id=correlation_id,
        origin_flow_run_id=None,
        user_id=probe_user_id,
        input_payload=FlowRunInput(user_input=user_line),
        interaction_id=uuid.uuid4(),
    )

    await rag.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            content=f"{user_line}\nrun_ref={uuid.uuid4().hex}",
            version="1.0",
            metadata={
                "scope": "TENANT_KNOWLEDGE",
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "description": "Criar ou registrar Despesa",
                "method": "POST",
                "path": "/createExpense",
                "tool_intent": ToolIntentFilter.COMMAND.value,
            },
        ),
    )
    reg = es.runtime.registry
    cls = reg.resolve(NodeType.ToolResolver.value)
    if cls is None:
        raise SystemExit("registry_resolve_tool_resolver_failed")
    node = cls()
    ctx = make_base_context(
        tenant_id=tenant_id,
        current_node_id=NODE_TOOL_SELECTION_ID,
        user_input=user_line,
        user_id=probe_user_id,
        flow_run_id=flow_run_id,
        session_id=session_id,
        correlation_id=correlation_id,
        flow_version_id=FLOW_VERSION_V1_ID,
    )
    cfg = {**llm_node_config(), "top_k": 5}
    res = await node.execute(ctx, cfg)
    if res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"tool_resolver_failed status={res.status!s} data={res.data!r}")
    payload = res.data if isinstance(res.data, dict) else {}
    items = payload.get("result") if isinstance(payload, dict) else None
    n = len(items) if isinstance(items, list) else 0
    print(
        "validate_node_tool_resolver: ok",
        f"selected_count={n}",
        f"data={json.dumps(payload, default=str)[:2000]}",
    )
    if n < 1:
        raise SystemExit(
            "tool_resolver_empty_selection: check RAG seeds, similarity_threshold, "
            "and agent_version.rag_config_id for NODE_TOOL_SELECTION_ID"
        )


if __name__ == "__main__":
    asyncio.run(main())
