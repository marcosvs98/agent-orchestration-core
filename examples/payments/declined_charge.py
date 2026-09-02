from __future__ import annotations

from typing import Final
from uuid import uuid4

from examples.api import PaymentsApiStub
from examples.api.runtime import await_settled, print_trace, start_flow_run, system_output
from examples.payments._common import load_payments_client, payments_stub_port, print_calls
from examples.support import expect, field, heading

LARGE_CHARGE: Final[str] = (
    "Charge customer cus_77310 2,500 US dollars on their card for the enterprise plan"
)


def main() -> None:
    print("A declined charge is a successful tool run with a refusal inside it")
    client, state = load_payments_client()

    with PaymentsApiStub(port=payments_stub_port(state)) as stub:
        field("upstream payments api", stub.base_url)
        print("  the stub declines card charges of 1000.00 or more, the way an issuer would:")
        print("  HTTP 201, status 'declined', decline_code 'insufficient_funds'.")

        heading("Charge an amount the issuer will refuse")
        run = start_flow_run(client, state, user_input=LARGE_CHARGE, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        field("system_output", system_output(final)[:140])
        print_trace(client, state, flow_run_id)
        print_calls(stub.calls_to("/v1/payments"), "POST /v1/payments calls")

        expect(
            final.get("status") == "COMPLETED",
            f"the flow run completed (got {final.get('status')})",
        )
        payments = stub.payments()
        expect(len(payments) == 1, f"the charge was attempted once (got {len(payments)})")
        payment = payments[0]
        field("upstream status", payment.status)
        field("decline_code", payment.decline_code)
        expect(payment.status == "declined", f"the issuer declined it (got {payment.status})")
        expect(
            payment.amount_captured_minor == 0,
            f"no money was captured (got {payment.amount_captured_minor})",
        )

        heading("What the graph did with it")
        print("  ToolExecutor reports SUCCESS because the HTTP call succeeded. The decline")
        print("  lives in the response body, so ToolErrorHandlerNode is never reached and no")
        print("  retry happens - which is correct here: retrying a declined card is harmful.")
        print("  Reading the decline out of the body is ResponseBuilder's job, and the only")
        print("  reason it can do that is the tenant knowledge document on declines.")

        trace = print_trace(client, state, flow_run_id)
        visited = {str(entry.get("node_id")) for entry in trace}
        node_ids = state.get("node_ids")
        expect(
            node_ids["ToolExecutor"] in visited,
            "ToolExecutor ran",
        )
        expect(
            node_ids["ToolErrorHandlerNode"] not in visited,
            "ToolErrorHandlerNode did not run, because the HTTP call itself succeeded",
        )
        expect(
            node_ids["ResponseBuilder"] in visited,
            "ResponseBuilder rendered the answer",
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
