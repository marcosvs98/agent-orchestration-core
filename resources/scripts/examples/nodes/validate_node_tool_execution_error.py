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
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.execution import FlowRunInput
from domain.execution.services.graph_runtime.registry import NodeRegistry
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.prompts.schemas.prompt import NodeType
from resources.scripts.examples.nodes.node_validation_context import make_base_context
from resources.scripts.seeds.demo.ids import (
    FLOW_VERSION_V1_ID,
    NODE_TOOL_EXEC_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


async def scenario_tool_error_handler(reg: NodeRegistry) -> None:
    h_cls = reg.resolve(NodeType.ToolErrorHandlerNode.value)
    if h_cls is None:
        raise SystemExit("registry_resolve_tool_error_handler_failed")
    h_node = h_cls()
    ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=uuid.uuid4(),
        user_input="",
        state={
            NodeType.ToolExecutor.value: {
                "result": [
                    {
                        "operation_id": "op_validate",
                        "tool_name": "createExpense",
                        "status": "error",
                        "result": {"message": "synthetic_tool_failure"},
                    }
                ]
            }
        },
    )
    res = await h_node.execute(ctx, {"max_retries": 0})
    if res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"tool_error_handler_failed {res.data!r}")
    if not res.data.get("fallback_required"):
        raise SystemExit("tool_error_handler_expected_fallback_required")
    print(
        "validate_node_tool_error_handler: ok",
        f"fallback_required={res.data.get('fallback_required')}",
        f"finalized={res.data.get('finalized_results_count')}",
    )


async def scenario_tool_execution(
    *,
    reg: NodeRegistry,
    repository: ExecutionRepository,
) -> None:
    e_cls = reg.resolve(NodeType.ToolExecutor.value)
    if e_cls is None:
        raise SystemExit("registry_resolve_tool_execution_failed")
    e_node = e_cls()
    correlation_id = uuid.uuid4()
    session_id = uuid.uuid4()
    flow_run_id = await repository.create_flow_run(
        session_id=session_id,
        flow_version_id=FLOW_VERSION_V1_ID,
        correlation_id=correlation_id,
        origin_flow_run_id=None,
        user_id="node_tool_validate",
        input_payload=FlowRunInput(user_input="tool_node_probe"),
        interaction_id=uuid.uuid4(),
    )
    node_run_id = await repository.create_node_run(
        flow_run_id=flow_run_id,
        node_id=NODE_TOOL_EXEC_ID,
        correlation_id=correlation_id,
        input_payload={},
        output_payload={},
        status="RUNNING",
        canonical_status="RUNNING",
    )
    ctx = make_base_context(
        tenant_id=TENANT_DEMO_ID,
        current_node_id=NODE_TOOL_EXEC_ID,
        user_input="execute seeded tool",
        current_node_run_id=node_run_id,
        state={
            NodeType.ToolInputFiller.value: {
                "result": [
                    {
                        "operation_id": "op_demo",
                        "tool_name": "createExpense",
                        "status": "ready",
                        "params": {"amount": 1, "note": "node_validation_probe"},
                    }
                ]
            },
            NodeType.ToolResolver.value: {
                "result": [
                    {
                        "selected_tool": {
                            "name": "createExpense",
                            "tool_id": str(TOOL_DEMO_ID),
                            "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                        }
                    }
                ]
            },
        },
    )
    res = await e_node.execute(ctx)
    if res.status != NodeExecutionStatus.SUCCESS:
        raise SystemExit(f"tool_execution_failed {res.error!r}")
    raw = res.data.get("result")
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f"tool_execution_expected_results got={res.data!r}")
    first = raw[0]
    st = first.get("status") if isinstance(first, dict) else None
    print(
        "validate_node_tool_execution: finished",
        f"first_status={st}",
    )


async def main() -> None:
    app = ApplicationContainer()
    es = app.execution.execution_service()
    reg = es.runtime.registry
    repository = app.execution.execution_repository()
    await scenario_tool_error_handler(reg)
    await scenario_tool_execution(reg=reg, repository=repository)


if __name__ == "__main__":
    asyncio.run(main())
