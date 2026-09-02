from __future__ import annotations

from typing import Final
from uuid import uuid4

from examples.api import PaymentsApiStub
from examples.api.runtime import await_settled, print_trace, start_flow_run, system_output
from examples.payments._common import load_payments_client, payments_stub_port, print_calls
from examples.support import expect, field, heading

CHARGE: Final[str] = (
    "Charge customer cus_10428 49.90 US dollars on their card for the annual subscription renewal"
)
REFUND: Final[str] = (
    "Refund 15.00 US dollars of payment {payment_id} back to the customer, they were charged twice"
)


def main() -> None:
    print("Charge a customer, then refund part of that payment")
    client, state = load_payments_client()

    with PaymentsApiStub(port=payments_stub_port(state)) as stub:
        field("upstream payments api", stub.base_url)
        print("  the tool_config stores an absolute base_url, so the stub has to own the same")
        print("  port it held during provisioning for ToolExecutor to reach it.")

        heading("Turn 1: take the money")
        charge_run = start_flow_run(client, state, user_input=CHARGE, session_id=str(uuid4()))
        charge_id = str(charge_run.get("id"))
        charge_final = await_settled(client, charge_id)
        field("terminal status", charge_final.get("status"))
        field("system_output", system_output(charge_final)[:88])
        print_trace(client, state, charge_id)
        print_calls(stub.calls_to("/v1/payments"), "POST /v1/payments calls")

        expect(
            charge_final.get("status") == "COMPLETED",
            f"the charge run reached COMPLETED (got {charge_final.get('status')})",
        )
        charges = [call for call in stub.calls_to("/v1/payments") if call.method == "POST"]
        expect(len(charges) == 1, f"the payments API was charged exactly once (got {len(charges)})")
        expect(
            charges[0].body.get("amount_minor") == 4990,
            f"49.90 was converted to 4990 minor units (got {charges[0].body.get('amount_minor')})",
        )
        expect(
            charges[0].body.get("currency") == "USD",
            f"the currency was extracted as USD (got {charges[0].body.get('currency')})",
        )
        expect(
            charges[0].authorization is not None,
            "the end-user Authorization header reached the upstream API",
        )

        payments = stub.payments()
        expect(len(payments) == 1, f"one payment exists upstream (got {len(payments)})")
        payment = payments[0]
        field("payment_id", payment.payment_id)
        field("status", payment.status)

        heading("Turn 2: give part of it back")
        print("  the payment id comes from the first turn, so this exercises the slot filler")
        print("  against an identifier it has never seen in any schema example.")
        refund_run = start_flow_run(
            client,
            state,
            user_input=REFUND.format(payment_id=payment.payment_id),
            session_id=str(uuid4()),
        )
        refund_id = str(refund_run.get("id"))
        refund_final = await_settled(client, refund_id)
        field("terminal status", refund_final.get("status"))
        field("system_output", system_output(refund_final)[:88])
        print_trace(client, state, refund_id)
        print_calls(stub.calls_to("/v1/refunds"), "POST /v1/refunds calls")

        expect(
            refund_final.get("status") == "COMPLETED",
            f"the refund run reached COMPLETED (got {refund_final.get('status')})",
        )
        refunds = stub.refunds()
        expect(len(refunds) == 1, f"exactly one refund was issued (got {len(refunds)})")
        expect(
            refunds[0].amount_minor == 1500,
            f"the refund was for 1500 minor units (got {refunds[0].amount_minor})",
        )
        expect(
            refunds[0].payment_id == payment.payment_id,
            "the refund targeted the payment created in turn 1",
        )

        settled = stub.payments()[0]
        field("payment status now", settled.status)
        expect(
            settled.status == "partially_refunded",
            f"the payment is partially_refunded (got {settled.status})",
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
