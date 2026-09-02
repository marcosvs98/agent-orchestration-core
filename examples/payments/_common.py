from __future__ import annotations

from typing import Any, Dict, List, Tuple

from examples.api.client import ApiClient
from examples.api.payments_api import RecordedCall
from examples.api.runtime import load_client, stub_port
from examples.api.state import DemoState
from examples.payments.setup import STATE_FILE
from examples.support import field


def load_payments_client() -> Tuple[ApiClient, DemoState]:
    return load_client(STATE_FILE)


def payments_stub_port(state: DemoState) -> int:
    return stub_port(state, "payments_api_base_url")


def print_call(call: RecordedCall) -> None:
    print(f"    {call.method} {call.path}")
    payload: Dict[str, Any] = call.body if call.body else dict(call.query)
    for key in sorted(payload):
        value = payload[key]
        if value in (None, "None"):
            continue
        print(f"      {key:.<28} {value}")


def print_calls(calls: List[RecordedCall], title: str) -> None:
    print()
    field(title, len(calls))
    for call in calls:
        print_call(call)
