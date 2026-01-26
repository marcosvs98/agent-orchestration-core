from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
resources_path = project_root / "resources"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from resources.scripts.seeds.demo.ids import (
    FLOW_DEMO_ID,
    FLOW_VERSION_V1_ID,
    TENANT_DEMO_ID,
)


def get_auth_token() -> str:
    token_from_env = os.getenv("AUTH_TOKEN")
    if token_from_env:
        return token_from_env

    python_cmd = "python3"
    venv_python = project_root / ".venv" / "bin" / "python3"
    if venv_python.exists():
        python_cmd = str(venv_python)

    try:
        env = {**os.environ, "PYTHONPATH": f"{project_root}/src", "ADMIN_TENANT_ID": str(TENANT_DEMO_ID)}
        result = subprocess.run(
            [python_cmd, str(project_root / "resources" / "generate_jwt_token.py")],
            cwd=project_root,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token and token != "YOUR_TOKEN_HERE":
                return token
    except Exception:
        pass

    print(
        "\n" + "=" * 60,
        file=sys.stderr,
    )
    print(
        "ERROR: Authentication token is required!",
        file=sys.stderr,
    )
    print(
        "\nTo generate a token, run:",
        file=sys.stderr,
    )
    print(
        "  make gen-admin-token",
        file=sys.stderr,
    )
    print(
        "\nOr set the AUTH_TOKEN environment variable:",
        file=sys.stderr,
    )
    print(
        "  export AUTH_TOKEN=$(make gen-admin-token)",
        file=sys.stderr,
    )
    print(
        "  make test-flow-demo",
        file=sys.stderr,
    )
    print(
        "=" * 60 + "\n",
        file=sys.stderr,
    )
    sys.exit(1)


def execute_flow_demo() -> None:
    conn = http.client.HTTPConnection("localhost", 8000)

    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())

    payload = json.dumps(
        {
            "session_id": session_id,
            "flow_id": str(FLOW_DEMO_ID),
            "flow_version_id": str(FLOW_VERSION_V1_ID),
            "origin_flow_run_id": None,
            "correlation_id": correlation_id,
            "input": {"user_input": "Gastei 1000 reais no mercado com o cartão XP"},
        }
    )

    auth_token = get_auth_token()

    headers = {
        "Idempotency-Key": idempotency_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }

    try:
        print(f"Executing flow run...")
        print(f"Flow ID: {FLOW_DEMO_ID}")
        print(f"Flow Version ID: {FLOW_VERSION_V1_ID}")
        print(f"Session ID: {session_id}")
        print(f"Correlation ID: {correlation_id}")
        print()

        conn.request("POST", "/core/v1/executions/flow-runs", payload, headers)
        res = conn.getresponse()
        data = res.read()
        response_text = data.decode("utf-8")

        print(f"Status: {res.status} {res.reason}")
        print(f"Response: {response_text}")

        if res.status == 201:
            response_json = json.loads(response_text)
            flow_run_id = response_json.get("id")
            print(f"\nFlow run created successfully!")
            print(f"Flow Run ID: {flow_run_id}")
            print(f"\nYou can check the flow run status with:")
            print(f"  GET /core/v1/executions/flow-runs/{flow_run_id}")
        else:
            print(f"\nError: Flow run creation failed")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    execute_flow_demo()
