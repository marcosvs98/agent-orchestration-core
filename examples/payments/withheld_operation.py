from __future__ import annotations

from typing import Final
from uuid import uuid4

from examples.api import PaymentsApiStub
from examples.api.runtime import await_settled, print_trace, start_flow_run, system_output
from examples.payments._common import load_payments_client, payments_stub_port, print_calls
from examples.support import expect, field, heading

PAYOUT_REQUEST: Final[str] = (
    "Pay out 4,800 US dollars of our settled balance to our own bank account ba_9921ff today"
)


def main() -> None:
    print("An imported-but-withheld operation cannot be reached from a conversation")
    client, state = load_payments_client()

    with PaymentsApiStub(port=payments_stub_port(state)) as stub:
        field("upstream payments api", stub.base_url)
        field("approved", ", ".join(state.get("approved_operation_ids")))
        field("withheld", ", ".join(state.get("withheld_operation_ids")))

        heading("Ask for the operation that was never approved")
        print("  payments_create_payout was imported from the same openapi.json as everything")
        print("  else, it still has a tool row, and provisioning deliberately indexed a catalog")
        print("  document for it - so this request DOES come back as a vector hit. Approval")
        print("  moved its tool_config out of PUBLISHED, and hydration keeps PUBLISHED configs")
        print("  only, so the hit is dropped before the resolver ever sees a candidate.")

        run = start_flow_run(client, state, user_input=PAYOUT_REQUEST, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        field("system_output", system_output(final)[:120])
        print_trace(client, state, flow_run_id)
        print_calls(stub.calls, "upstream calls")

        expect(
            final.get("status") == "COMPLETED",
            f"the run still completed cleanly (got {final.get('status')})",
        )
        payouts = stub.calls_to("/v1/payouts")
        expect(len(payouts) == 0, f"no payout was created upstream (got {len(payouts)})")
        write_methods = {call.method for call in stub.calls} - {"GET"}
        expect(
            not write_methods,
            f"every call the assistant made was read-only (got {sorted(write_methods)})",
        )
        print()
        print("  the resolver did not simply give up: the withheld hit was dropped and an")
        print("  APPROVED tool was selected instead. The refusal itself comes from the tenant")
        print("  knowledge document on payouts, not from any hard-coded branch in the graph.")

        heading("The catalog still lists it, the approval state is what blocks it")
        configs = client.get(
            "/core/v1/tool-configs",
            params={"limit": 200},
            label="list tool configs",
        )
        by_operation = {
            str((config.get("config") or {}).get("operation_id")): str(config.get("status"))
            for config in configs
        }
        for operation_id in sorted(by_operation):
            field(operation_id, by_operation[operation_id])

        for operation_id in state.get("withheld_operation_ids"):
            expect(
                by_operation.get(operation_id) == "DISABLED",
                f"{operation_id} is DISABLED (got {by_operation.get(operation_id)})",
            )
        for operation_id in state.get("approved_operation_ids"):
            expect(
                by_operation.get(operation_id) == "PUBLISHED",
                f"{operation_id} is PUBLISHED (got {by_operation.get(operation_id)})",
            )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
