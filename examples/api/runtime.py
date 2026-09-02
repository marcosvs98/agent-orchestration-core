from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set, Tuple
from uuid import uuid4

from examples.api.client import ApiClient
from examples.api.state import DEFAULT_STATE_FILE, DemoState

TERMINAL_STATUSES: Final[Set[str]] = {"COMPLETED", "FAILED", "CANCELLED"}
SETTLED_STATUSES: Final[Set[str]] = TERMINAL_STATUSES | {"WAITING_INPUT"}

END_USER_AUTHORIZATION_KEY: Final[str] = "end_user_authorization"


def tool_call_metadata(token: str = "Bearer examples-end-user-token") -> Dict[str, Any]:
    return {END_USER_AUTHORIZATION_KEY: token}


def load_client(state_file: Path = DEFAULT_STATE_FILE) -> Tuple[ApiClient, DemoState]:
    state = DemoState(state_file).load()
    client = ApiClient(state.get("base_url"), state.get("tenant_token"))
    return client, state


def start_flow_run(
    client: ApiClient,
    state: DemoState,
    *,
    user_input: str,
    user_id: str = "examples-user",
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    wait: bool = True,
) -> Dict[str, Any]:
    return client.post(
        "/core/v1/executions/flow-runs",
        {
            "session_id": session_id or str(uuid4()),
            "user_id": user_id,
            "flow_id": state.get("flow_id"),
            "input": {"user_input": user_input},
            "metadata": tool_call_metadata() if metadata is None else metadata,
        },
        params={"wait": "true" if wait else "false"},
        label=f"flow run: {user_input[:38]!r}",
        idempotent=True,
    )


def await_settled(
    client: ApiClient, flow_run_id: str, timeout_seconds: int = 120
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    run: Dict[str, Any] = {}
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        run = client.get(
            f"/core/v1/executions/flow-runs/{flow_run_id}",
            label=f"poll flow run ({attempt})",
        )
        if run.get("status") in SETTLED_STATUSES:
            return run
        time.sleep(2)
    return run


def node_runs(client: ApiClient, flow_run_id: str) -> List[Dict[str, Any]]:
    result = client.get(
        "/core/v1/executions/node-runs",
        params={"flow_run_id": flow_run_id, "limit": 200},
        label="list node runs",
    )
    return result if isinstance(result, list) else []


def execution_events(client: ApiClient, flow_run_id: str) -> List[Dict[str, Any]]:
    result = client.get(
        "/core/v1/executions/execution-events",
        params={"flow_run_id": flow_run_id, "limit": 200},
        label="list execution events",
    )
    return result if isinstance(result, list) else []


def stub_port(state: DemoState, key: str) -> int:
    return int(str(state.get(key)).rsplit(":", 1)[-1])


def node_type_by_id(state: DemoState) -> Dict[str, str]:
    return {node_id: node_type for node_type, node_id in state.get("node_ids").items()}


def print_trace(client: ApiClient, state: DemoState, flow_run_id: str) -> List[Dict[str, Any]]:
    names = node_type_by_id(state)
    runs = node_runs(client, flow_run_id)
    ordered = sorted(runs, key=lambda run: str(run.get("started_at") or ""))
    print()
    print("  node trace")
    for run in ordered:
        node_type = names.get(str(run.get("node_id")), "?")
        print(f"    {node_type:<22} {run.get('status'):<10} {str(run.get('id'))[:8]}")
    return ordered


def system_output(run: Dict[str, Any]) -> str:
    return str((run.get("output") or {}).get("system_output") or "")
