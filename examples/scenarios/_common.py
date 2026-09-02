from __future__ import annotations

from examples.api.runtime import (
    END_USER_AUTHORIZATION_KEY,
    SETTLED_STATUSES,
    TERMINAL_STATUSES,
    await_settled,
    execution_events,
    load_client,
    node_runs,
    node_type_by_id,
    print_trace,
    start_flow_run,
    stub_port,
    system_output,
    tool_call_metadata,
)
from examples.api.state import DemoState

__all__ = [
    "END_USER_AUTHORIZATION_KEY",
    "SETTLED_STATUSES",
    "TERMINAL_STATUSES",
    "await_settled",
    "execution_events",
    "expense_stub_port",
    "load_client",
    "node_runs",
    "node_type_by_id",
    "print_trace",
    "start_flow_run",
    "system_output",
    "tool_call_metadata",
]


def expense_stub_port(state: DemoState) -> int:
    return stub_port(state, "expense_api_base_url")
