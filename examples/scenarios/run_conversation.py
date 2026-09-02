from __future__ import annotations

from typing import Final
from uuid import uuid4

from examples.api import ExpenseApiStub
from examples.scenarios._common import (
    await_settled,
    expense_stub_port,
    load_client,
    print_trace,
    start_flow_run,
)
from examples.support import expect, field, heading

COMPLETE_COMMAND: Final[str] = (
    "I paid 120 dollars at the supermarket today, Chase debit card, personal account, "
    "category groceries, description weekly supermarket run"
)


def main() -> None:
    print("Run the provisioned flow end to end")
    client, state = load_client()

    with ExpenseApiStub(port=expense_stub_port(state)) as stub:
        field("upstream tool api", stub.base_url)
        print("  the tool_config was imported with this origin, so the stub must own the")
        print("  same port it had during provisioning for ToolExecutor to reach it.")

        heading("A command that resolves a tool and executes it")
        print("  The flow run carries metadata['end_user_authorization']: import-tools")
        print("  always binds the upstream Authorization header to that interaction metadata")
        print("  key, so without it every tool call fails interaction_metadata_header_missing.")
        run = start_flow_run(client, state, user_input=COMPLETE_COMMAND, session_id=str(uuid4()))
        flow_run_id = str(run.get("id"))
        field("flow_run_id", flow_run_id)

        final = await_settled(client, flow_run_id)
        field("terminal status", final.get("status"))
        field("system_output", str((final.get("output") or {}).get("system_output"))[:88])

        print_trace(client, state, flow_run_id)

        calls = [c for c in stub.calls if c["path"].rstrip("/") == "/createExpense"]
        print()
        field("createExpense calls", len(calls))
        if calls:
            body = calls[0]["body"]
            field("amount", body.get("amount"))
            field("currency", body.get("currency"))
            field("description", str(body.get("description"))[:52])
            field("payment_method", body.get("payment_method"))

        expect(
            final.get("status") == "COMPLETED",
            f"the run reached COMPLETED (got {final.get('status')})",
        )
        expect(len(calls) == 1, f"the upstream tool was called exactly once (got {len(calls)})")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
