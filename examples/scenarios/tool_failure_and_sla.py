from __future__ import annotations

import json
from typing import Any, Dict, Final, Iterator, Sequence
from uuid import uuid4

from examples.api import ExpenseApiStub
from examples.scenarios._common import (
    await_settled,
    execution_events,
    expense_stub_port,
    load_client,
    print_trace,
    start_flow_run,
)
from examples.support import expect, field, heading

COMMAND: Final[str] = (
    "I paid 87 dollars at the pharmacy today, Chase credit card, personal account, "
    "category health, description prescription medicine"
)


def _payload_of(
    events: Sequence[Dict[str, Any]],
    event_type: str,
    node_id: str | None = None,
) -> Iterator[Dict[str, Any]]:
    for event in events:
        if event.get("type") != event_type:
            continue
        payload = event.get("payload") or {}
        if node_id is None or payload.get("node_id") == node_id:
            yield payload


def main() -> None:
    print("A failing upstream: bounded retry, then human escalation")
    client, state = load_client()
    nodes = state.get("node_ids")

    with ExpenseApiStub(port=expense_stub_port(state)) as stub:
        field("upstream tool api", stub.base_url)

        heading("Make every upstream call fail")
        stub.fail_next_calls(10, mode="hangup")
        field("forced failures", 10)
        field("failure mode", "connection hangup (transport error)")
        print('  ToolErrorHandlerNode config is {"max_retries": 1}, so the graph gets one')
        print("  retry pass and then routes to HumanFallback.")
        print()
        print("  The stub hangs up rather than returning 503 on purpose. HttpToolExecutor")
        print("  never calls raise_for_status, and tool_orchestrator writes ToolRunStatus.")
        print("  SUCCESS for ANY response it receives - so an upstream 4xx/5xx is recorded")
        print("  as a successful tool run and never reaches this retry path. Only transport")
        print("  level failures (timeout, hangup) are classified as errors today.")

        run = start_flow_run(client, state, user_input=COMMAND, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        field("system_output", str((final.get("output") or {}).get("system_output"))[:88])

        trace = print_trace(client, state, flow_run_id)
        visited = [row for row in trace]
        executor_runs = [r for r in visited if str(r.get("node_id")) == nodes["ToolExecutor"]]

        print()
        field("upstream calls", len(stub.calls))
        field("ToolExecutor node runs", len(executor_runs))
        expect(
            len(stub.calls) == 2,
            f"the tool ran twice: original + one retry (got {len(stub.calls)})",
        )
        expect(len(executor_runs) == 2, "ToolExecutor executed twice")

        heading("What the error handler decided")
        events = execution_events(client, flow_run_id)
        handler_payloads = list(_payload_of(events, "NodeCompleted", nodes["ToolErrorHandlerNode"]))
        for index, payload in enumerate(handler_payloads, start=1):
            inner = payload.get("payload") or {}
            print(
                f"    pass {index}: retry_operation_ids={inner.get('retry_operation_ids')} "
                f"fallback_required={inner.get('fallback_required')}"
            )
        expect(len(handler_payloads) == 2, "the error handler ran on both passes")
        last = handler_payloads[-1].get("payload") or {}
        expect(last.get("fallback_required") is True, "the second pass escalated to a human")

        heading("The SLA case that was opened")
        cases = client.get(
            "/core/v1/sla-cases",
            params={"status": "OPEN", "limit": 50},
            label="list open sla cases",
        )
        mine = [c for c in cases if str(c.get("flow_run_id")) == flow_run_id]
        field("open cases for this run", len(mine))
        if mine:
            case = mine[0]
            field("node", case.get("node"))
            field("fallback_reason", case.get("fallback_reason"))
            field("priority", case.get("priority"))
            expect(
                case.get("fallback_reason") == "TOOL_FAILURE",
                f"the reason is TOOL_FAILURE, not the LOW_CONFIDENCE default "
                f"(got {case.get('fallback_reason')})",
            )
        else:
            print("  no SLA case row was returned; raw response:")
            print("  " + json.dumps(cases)[:300])

    print()
    print("Done.")


if __name__ == "__main__":
    main()
