from __future__ import annotations

from typing import Final
import json
from collections import Counter
from uuid import uuid4

from examples.api import ExpenseApiStub
from examples.scenarios._common import (
    await_settled,
    execution_events,
    expense_stub_port,
    load_client,
    node_type_by_id,
    start_flow_run,
)
from examples.support import expect, field, heading

COMMAND: Final[str] = (
    "I paid 32 dollars for lunch today, Chase debit card, personal account, "
    "category meals, description lunch"
)


def main() -> None:
    print("What the platform records about a single turn")
    client, state = load_client()
    names = node_type_by_id(state)

    with ExpenseApiStub(port=expense_stub_port(state)):
        run = start_flow_run(client, state, user_input=COMMAND, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)

    heading("1. The flow run record")
    for key in (
        "id",
        "status",
        "canonical_status",
        "flow_version_id",
        "flow_graph_snapshot_id",
        "correlation_id",
        "trace_id",
        "execution_plan_hash",
        "runtime_policy_hash",
        "temporal_workflow_id",
        "failure_reason",
    ):
        field(key, final.get(key))
    print("  temporal_workflow_id is null because TEMPORAL_ENABLED defaults to false;")
    print("  the turn ran inline in the HTTP request.")

    heading("2. Node runs")
    node_runs = client.get(
        "/core/v1/executions/node-runs",
        params={"flow_run_id": flow_run_id, "limit": 200},
        label="list node runs",
    )
    for row in sorted(node_runs, key=lambda r: str(r.get("started_at") or "")):
        field(names.get(str(row.get("node_id")), "?"), row.get("status"))

    heading("3. Execution events")
    events = execution_events(client, flow_run_id)
    counts = Counter(str(e.get("type")) for e in events)
    for event_type, count in counts.most_common():
        field(event_type, count)
    field("total events", len(events))

    heading("4. Graph state")
    graph_state = client.get(
        f"/core/v1/executions/flow-runs/{flow_run_id}/graph-state",
        label="get graph state",
    )
    state_keys = sorted((graph_state or {}).get("state", {}))
    field("state keys", ", ".join(state_keys)[:88] or "(none)")

    heading("5. Agent runs")
    agent_runs = client.get(
        "/core/v1/executions/agent-runs",
        params={"flow_run_id": flow_run_id, "limit": 200},
        label="list agent runs",
    )
    field("agent_run rows", len(agent_runs) if isinstance(agent_runs, list) else agent_runs)
    print("  The graph runtime never creates agent_run rows, so per-node token counts and")
    print("  estimated_cost columns stay empty. LLM token usage is visible only in the")
    print("  NodeCompleted event metrics below, and in Langfuse when tracing is enabled.")

    heading("6. Token usage recorded on node events")
    total_in = 0
    total_out = 0
    for event in events:
        payload = event.get("payload") or {}
        metrics = payload.get("metrics") or {}
        if not isinstance(metrics, dict) or not metrics:
            continue
        node = names.get(str(payload.get("node_id")), "?")
        total_in += int(metrics.get("input_tokens") or 0)
        total_out += int(metrics.get("output_tokens") or 0)
        field(node, f"in={metrics.get('input_tokens')} out={metrics.get('output_tokens')}")
    field("total", f"in={total_in} out={total_out}")

    heading("7. Interactions and sessions")
    sessions = client.get(
        "/core/v1/sessions",
        params={"user_id": "examples-user", "limit": 10},
        label="list sessions",
    )
    items = sessions.get("items") if isinstance(sessions, dict) else sessions
    field("sessions for the user", len(items) if isinstance(items, list) else items)
    print("  note: /sessions returns {items, limit, offset, has_next} while the execution")
    print("        list endpoints return bare arrays - pagination is not consistent.")

    expect(len(events) > 0, "the turn produced execution events")
    expect(len(node_runs) > 0, "the turn produced node runs")
    expect(
        isinstance(agent_runs, list) and len(agent_runs) == 0,
        f"agent runs are empty as documented (got {json.dumps(agent_runs)[:80]})",
    )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
