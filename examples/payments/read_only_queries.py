from __future__ import annotations

from typing import Any, Dict, Final, List, Sequence
from uuid import uuid4

import httpx

from examples.api import PaymentsApiStub
from examples.api.runtime import await_settled, print_trace, start_flow_run, system_output
from examples.payments._common import load_payments_client, payments_stub_port, print_calls
from examples.support import expect, field, heading

STOREFRONT_PAYMENTS: Final[Sequence[Dict[str, Any]]] = (
    {
        "amount_minor": 4990,
        "currency": "USD",
        "payment_method": "card",
        "customer_reference": "cus_10428",
        "description": "Annual subscription renewal",
    },
    {
        "amount_minor": 1250,
        "currency": "USD",
        "payment_method": "wallet",
        "customer_reference": "cus_10428",
        "description": "Add-on seat",
    },
    {
        "amount_minor": 89900,
        "currency": "USD",
        "payment_method": "bank_transfer",
        "customer_reference": "cus_55021",
        "description": "Invoice INV-2211",
    },
)

BALANCE_QUESTION: Final[str] = "How much money do we have available in US dollars right now?"
LIST_QUESTION: Final[str] = "Show me the payments we have collected from customer cus_10428"


def seed_storefront(stub: PaymentsApiStub) -> None:
    headers = {"Authorization": "Bearer storefront-service-token"}
    with httpx.Client(timeout=10.0) as client:
        for payload in STOREFRONT_PAYMENTS:
            response = client.post(
                f"{stub.base_url}/v1/payments", json=dict(payload), headers=headers
            )
            response.raise_for_status()


def main() -> None:
    print("Answer read-only questions with GET tools")
    client, state = load_payments_client()

    with PaymentsApiStub(port=payments_stub_port(state)) as stub:
        field("upstream payments api", stub.base_url)

        heading("The storefront already took these payments")
        seed_storefront(stub)
        for payment in stub.payments():
            summary = f"{payment.amount_minor} {payment.currency} {payment.description}"
            field(payment.payment_id, summary)
        baseline = len(stub.calls)

        heading("Question 1: what is the balance")
        print("  a GET tool: HttpToolExecutor turns the filled slots into query parameters")
        print("  instead of a JSON body, and no money moves.")
        balance_run = start_flow_run(
            client, state, user_input=BALANCE_QUESTION, session_id=str(uuid4())
        )
        balance_id = str(balance_run.get("id"))
        balance_final = await_settled(client, balance_id)
        field("terminal status", balance_final.get("status"))
        field("system_output", system_output(balance_final)[:88])
        print_trace(client, state, balance_id)

        heading("Question 2: what has this customer paid")
        list_run = start_flow_run(client, state, user_input=LIST_QUESTION, session_id=str(uuid4()))
        list_id = str(list_run.get("id"))
        list_final = await_settled(client, list_id)
        field("terminal status", list_final.get("status"))
        field("system_output", system_output(list_final)[:88])
        print_trace(client, state, list_id)

        agent_calls = stub.calls[baseline:]
        print_calls(agent_calls, "calls made by the assistant")

        expect(
            balance_final.get("status") == "COMPLETED",
            f"the balance run reached COMPLETED (got {balance_final.get('status')})",
        )
        expect(
            list_final.get("status") == "COMPLETED",
            f"the list run reached COMPLETED (got {list_final.get('status')})",
        )
        methods = {call.method for call in agent_calls}
        expect(
            methods == {"GET"},
            f"the assistant only issued read-only calls (got {sorted(methods)})",
        )
        paths = [call.path for call in agent_calls]
        expect(
            "/v1/balance" in paths,
            f"the balance question resolved payments_get_balance (paths: {paths})",
        )
        expect(
            "/v1/payments" in paths,
            f"the customer question resolved payments_list_payments (paths: {paths})",
        )
        expect(
            len(stub.payments()) == len(STOREFRONT_PAYMENTS),
            "no new payment was created while answering questions",
        )

        listed: List[str] = [
            call.query.get("customer_reference", "")
            for call in agent_calls
            if call.path == "/v1/payments"
        ]
        expect(
            "cus_10428" in listed,
            f"the customer reference was passed as a query parameter (got {listed})",
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()
