from __future__ import annotations

from typing import Any, Dict, Final
from uuid import uuid4

from examples.api import ApiClient, DemoState, ExpenseApiStub, require_id
from examples.api.provisioning import GRAPH_NODE_TYPES, build_graph_definition
from examples.scenarios._common import (
    await_settled,
    execution_events,
    expense_stub_port,
    load_client,
    print_trace,
    start_flow_run,
)
from examples.support import expect, field, heading

DELAY_SECONDS: Final[int] = 900
COMMAND: Final[str] = (
    "I paid 45 dollars for parking today, Chase credit card, personal account, "
    "category transport, description downtown parking garage"
)


def provision_scheduled_version(client: ApiClient, state: DemoState) -> Dict[str, Any]:
    flow_id = state.get("flow_id")
    rag_config_id = state.get("rag_config_id")
    prompt_ids = state.get("node_prompt_ids")

    existing = client.get(
        f"/core/v1/flows/{flow_id}/versions",
        label="list existing flow versions",
    )
    used = {
        (v.get("version_major"), v.get("version_minor"), v.get("version_patch"))
        for v in existing
        if isinstance(v, dict)
    }
    minor = 0
    while (2, minor, 0) in used:
        minor += 1
    field("new version", f"2.{minor}.0")
    print("  note: (major, minor, patch) is unique per flow and a duplicate raises an")
    print("        uncaught IntegrityError that surfaces as 500, so pick a free one.")

    version = client.post(
        f"/core/v1/flows/{flow_id}/versions",
        {
            "version_major": 2,
            "version_minor": minor,
            "version_patch": 0,
            "min_agent_version_major": 1,
            "min_agent_version_minor": 0,
            "min_agent_version_patch": 0,
        },
        label="create flow version 2",
    )
    flow_version_id = require_id(version, "id", "flow version 2")

    nodes: Dict[str, str] = {}
    for node_type in GRAPH_NODE_TYPES:
        body: Dict[str, Any] = {
            "flow_id": flow_id,
            "flow_version_id": flow_version_id,
            "node_type": node_type,
            "node_prompt_id": prompt_ids[node_type],
            "allow_rag_tenant": True,
            "allow_session_context": True,
            "rag_config_id": rag_config_id,
        }
        if node_type == "MemoryCommitNode":
            body["allow_memory_write"] = True
            body["allow_user_memory_structured"] = True
            body["config"] = {
                "schema_id": "user.preference.v1",
                "schema_version": 1,
                "source": "explicit_user",
                "rag_config_id": rag_config_id,
            }
        created = client.post(
            f"/core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:custom",
            body,
            label=f"v2 node {node_type}",
        )
        nodes[node_type] = require_id(created, "id", f"v2 node {node_type}")

    scheduling = {
        "scheduling": {
            "mode": "scheduled",
            "delay_seconds": DELAY_SECONDS,
            "tool_names": [state.get("tool_name")],
        }
    }
    definition = build_graph_definition(nodes, rag_config_id, tool_executor_config=scheduling)
    base = f"/core/v1/flows/{flow_id}/versions/{flow_version_id}"

    client.post(
        f"{base}/graph:draft",
        {
            "flow_id": flow_id,
            "flow_version_id": flow_version_id,
            "principal_id": "examples",
            "definition": definition,
        },
        label="upsert v2 graph draft",
    )
    client.post(
        f"{base}/graph:validate",
        {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": "examples"},
        label="validate v2 graph draft",
    )
    client.post(f"{base}:validate", label="validate flow version 2")
    client.post(
        f"{base}:publish",
        {"change_type": "PUBLISH", "justification": "scheduled tool execution example"},
        label="publish flow version 2",
    )
    client.post(
        f"{base}/graph:compile",
        {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": "examples"},
        label="compile v2 snapshot",
    )
    client.post(
        f"{base}:activate",
        {"change_type": "ACTIVATE", "justification": "scheduled tool execution example"},
        label="activate flow version 2",
    )
    return {"flow_version_id": flow_version_id, "node_ids": nodes}


def main() -> None:
    print("ToolExecutionMode.SCHEDULED through the graph")
    client, state = load_client()

    heading("1. Publish a second flow version whose ToolExecutor schedules")
    print(f"  scheduling = mode=scheduled, delay_seconds={DELAY_SECONDS}")
    print("  Activating v2 demotes v1: a flow has exactly one active version, and")
    print("  create-flow-run resolves the active one.")
    version = provision_scheduled_version(client, state)
    field("flow_version_id", version["flow_version_id"])

    scheduled_state = DemoState()
    scheduled_state.values = dict(state.values)
    scheduled_state.set("node_ids", version["node_ids"])

    with ExpenseApiStub(port=expense_stub_port(state)) as stub:
        heading("2. Run a turn that resolves the tool")
        run = start_flow_run(client, state, user_input=COMMAND, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        print_trace(client, scheduled_state, flow_run_id)

        heading("3. The side effect was deferred, not executed")
        events = execution_events(client, flow_run_id)
        executor_payload: Dict[str, Any] = {}
        for event in events:
            payload = event.get("payload") or {}
            if payload.get("node_id") == version["node_ids"]["ToolExecutor"]:
                inner = payload.get("payload") or {}
                if isinstance(inner.get("result"), list) and inner["result"]:
                    executor_payload = inner["result"][0]

        field("execution_mode", executor_payload.get("execution_mode"))
        field("status", executor_payload.get("status"))
        field("schedule_id", executor_payload.get("schedule_id"))
        field("run_at", executor_payload.get("run_at"))
        field("upstream calls", len(stub.calls))

        expect(
            executor_payload.get("execution_mode") == "scheduled",
            "the operation was scheduled rather than executed inline",
        )
        expect(len(stub.calls) == 0, "the upstream tool has NOT been called yet")
        expect(
            bool(executor_payload.get("schedule_id")),
            "a durable schedule id was returned",
        )

    print()
    print("  The schedule is a Temporal workflow parked on a durable server-side timer.")
    print("  Start a worker to let it fire:  make worker")
    print(
        f"  Inspect it at http://localhost:8233 (workflow id {executor_payload.get('schedule_id')})"
    )

    heading("4. Restore the immediate version as active")
    client.post(
        f"/core/v1/flows/{state.get('flow_id')}/versions/{state.get('flow_version_id')}:activate",
        {"change_type": "ACTIVATE", "justification": "restore immediate execution"},
        label="re-activate flow version 1",
    )
    print("  so the other scenarios keep executing tools inline.")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
