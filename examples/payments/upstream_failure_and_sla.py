from __future__ import annotations

from typing import Final
import json
from uuid import uuid4

from examples.api import PaymentsApiStub
from examples.api.runtime import await_settled, print_trace, start_flow_run, system_output
from examples.payments._common import load_payments_client, payments_stub_port, print_calls
from examples.support import expect, field, heading

CHARGE: Final[str] = "Charge customer cus_55021 75.00 US dollars on their card for invoice INV-2211"


def main() -> None:
    print("An unreachable payments API: one bounded retry, then escalation to a human")
    client, state = load_payments_client()

    with PaymentsApiStub(port=payments_stub_port(state)) as stub:
        field("upstream payments api", stub.base_url)

        heading("Make every attempt drop the connection")
        stub.fail_next_calls(9, mode="hangup")
        print("  the stub answers, starts streaming and then closes the socket, which httpx")
        print("  surfaces as RemoteProtocolError - a transport error, not an HTTP status.")
        print("  Only transport failures reach the retry and fallback path: an upstream 5xx is")
        print("  recorded as a successful tool run, which is a known gap, not a design choice.")

        run = start_flow_run(client, state, user_input=CHARGE, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        field("system_output", system_output(final)[:140])
        trace = print_trace(client, state, flow_run_id)
        print_calls(stub.calls_to("/v1/payments"), "POST /v1/payments attempts")

        attempts = [call for call in stub.calls_to("/v1/payments") if call.method == "POST"]
        expect(
            len(attempts) == 2,
            f"the tool ran twice - the original plus one bounded retry (got {len(attempts)})",
        )
        expect(
            len(stub.payments()) == 0,
            f"no payment was ever created upstream (got {len(stub.payments())})",
        )

        node_ids = state.get("node_ids")
        visited = {str(entry.get("node_id")) for entry in trace}
        expect(
            node_ids["ToolErrorHandlerNode"] in visited,
            "ToolErrorHandlerNode ran and bounded the retries at max_retries=1",
        )
        expect(node_ids["HumanFallback"] in visited, "HumanFallback took over after the retry")

        heading("The SLA case the fallback opened")
        cases = client.get(
            "/core/v1/sla-cases",
            params={"status": "OPEN", "limit": 50},
            label="list open sla cases",
        )
        mine = [case for case in cases if str(case.get("flow_run_id")) == flow_run_id]
        field("open cases for this run", len(mine))
        if not mine:
            print("  no SLA case row was returned; raw response:")
            print("  " + json.dumps(cases)[:300])
        for case in mine:
            field("node", case.get("node"))
            field("fallback_reason", case.get("fallback_reason"))
            field("priority", case.get("priority"))
            expect(
                case.get("fallback_reason") == "TOOL_FAILURE",
                f"the reason is TOOL_FAILURE, not the LOW_CONFIDENCE default "
                f"(got {case.get('fallback_reason')})",
            )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
