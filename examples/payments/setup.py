from __future__ import annotations

import os
from typing import Final
from uuid import uuid4

from examples.api import ApiClient, DemoState, PaymentsApiStub, mint_admin_token, require_id
from examples.api.provisioning import (
    require_healthy_api,
    stage_ai_policy,
    stage_bindings,
    stage_governance,
    stage_graph,
    stage_import_and_approve_tools,
    stage_ingest,
    stage_llm_provider,
    stage_mcp_server,
    stage_models,
    stage_nodes,
    stage_prompts,
    stage_publish_rag,
    stage_rag,
    stage_runtime_policy,
    stage_tenant_token,
)
from examples.api.state import STATE_DIR
from examples.payments.knowledge import (
    AGENT_SYSTEM_PROMPT,
    APPROVED_OPERATION_IDS,
    KNOWLEDGE_DOCUMENTS,
    TOOL_ALIAS_CLUSTERS,
    WITHHELD_OPERATION_IDS,
)
from examples.support import field, heading

BASE_URL: Final[str] = os.environ.get("AOC_BASE_URL", "http://127.0.0.1:8000")
STATE_FILE: Final = STATE_DIR / "payments_tenant_setup.json"


def stage_tenant(client: ApiClient, state: DemoState, suffix: str) -> None:
    heading("Tenant")
    tenant = client.post(
        "/core/v1/tenants",
        {
            "name": f"Acme Payments Operations {suffix}",
            "external_id": str(uuid4()),
            "description": "Tenant provisioned by examples/payments/setup.py",
            "timezone": "UTC",
            "is_active": True,
            "currency": "USD",
            "language": "en_US",
            "settings": {},
        },
        label="create tenant",
    )
    state.set("tenant_id", require_id(tenant, "id", "create tenant"))
    field("tenant_id", state.get("tenant_id"))


def stage_agent(client: ApiClient, state: DemoState) -> None:
    heading("Agent and agent version")
    agent = client.post("/core/v1/agents", {"name": "PaymentsOperator"}, label="create agent")
    agent_id = require_id(agent, "id", "agent")
    version = client.post(
        f"/core/v1/agents/{agent_id}/versions",
        {
            "description": "Payments operations assistant v1",
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
            "persona_config": {"tone": "professional", "style": "concise", "language": "en_US"},
            "system_prompt": AGENT_SYSTEM_PROMPT,
        },
        label="create agent version",
    )
    agent_version_id = require_id(version, "id", "agent version")
    client.post(
        f"/core/v1/agents/{agent_id}/versions/{agent_version_id}:validate",
        label="validate agent version",
    )
    client.post(
        f"/core/v1/agents/{agent_id}/versions/{agent_version_id}:publish",
        {"change_type": "PUBLISH", "justification": "examples bootstrap"},
        label="publish agent version",
    )
    client.post(
        f"/core/v1/agents/{agent_id}/versions/{agent_version_id}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate agent version",
    )
    state.set("agent_id", agent_id)
    state.set("agent_version_id", agent_version_id)


def stage_flow(client: ApiClient, state: DemoState) -> None:
    heading("Flow and flow version")
    flow = client.post(
        "/core/v1/flows",
        {
            "name": "payments-operations-flow",
            "description": "Moderation, tool resolution, slot filling, execution, response.",
        },
        label="create flow",
    )
    flow_id = require_id(flow, "id", "flow")
    version = client.post(
        f"/core/v1/flows/{flow_id}/versions",
        {
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
            "min_agent_version_major": 1,
            "min_agent_version_minor": 0,
            "min_agent_version_patch": 0,
        },
        label="create flow version",
    )
    state.set("flow_id", flow_id)
    state.set("flow_version_id", require_id(version, "id", "flow version"))


def stage_user_prompt(client: ApiClient) -> str:
    heading("User prompt")
    prompt = client.post(
        "/core/v1/user-prompts",
        {
            "title": "payments_operations_default",
            "content": (
                "Confirm the amount, the currency and the customer before moving money. If the "
                "request is ambiguous, ask exactly one direct clarification question."
            ),
            "created_by": "examples",
        },
        label="create user prompt",
    )
    return require_id(prompt, "id", "user prompt")


def main() -> None:
    print("Provision a tenant around a market-standard payments API")
    print(f"api = {BASE_URL}")

    wait_seconds = int(os.environ.get("AOC_INGEST_WAIT_SECONDS", "45"))
    suffix = uuid4().hex[:8]
    state = DemoState(STATE_FILE)

    with PaymentsApiStub() as stub:
        field("upstream payments api", stub.base_url)
        print("  a real FastAPI app running in this process; the orchestrator fetches its")
        print("  openapi.json server-side, so it has to be reachable from the API host.")

        token = mint_admin_token()
        with ApiClient(BASE_URL, token) as client:
            require_healthy_api(client, BASE_URL)

            stage_tenant(client, state, suffix)
            stage_tenant_token(client, state)
            stage_models(client, state)
            stage_llm_provider(client, state)
            stage_ai_policy(client, state)
            stage_rag(client, state, suffix)
            stage_publish_rag(client, state)
            imported = stage_import_and_approve_tools(
                client,
                state,
                openapi_url=stub.openapi_url,
                approved_operation_ids=APPROVED_OPERATION_IDS,
            )
            stage_ingest(
                client,
                state,
                knowledge_documents=KNOWLEDGE_DOCUMENTS,
                tool_aliases=TOOL_ALIAS_CLUSTERS,
                imported_tools=imported,
                wait_seconds=wait_seconds,
            )
            stage_agent(client, state)
            stage_prompts(client, state)
            stage_flow(client, state)
            stage_nodes(client, state)
            stage_graph(client, state)
            stage_bindings(client, state)
            stage_runtime_policy(client, state)
            stage_governance(client, state)
            stage_mcp_server(client, state, user_prompt_id=stage_user_prompt(client))

            state.set("base_url", BASE_URL)
            state.set("payments_api_base_url", stub.base_url)
            state.save()

    heading("Provisioned")
    field("tenant_id", state.get("tenant_id"))
    field("flow_id", state.get("flow_id"))
    field("agent_id", state.get("agent_id"))
    field("approved tools", ", ".join(state.get("approved_operation_ids")))
    field("withheld tools", ", ".join(state.get("withheld_operation_ids")) or "-")
    field("state file", str(state.path))

    expected_withheld = sorted(WITHHELD_OPERATION_IDS)
    actual_withheld = sorted(state.get("withheld_operation_ids"))
    if actual_withheld != expected_withheld:
        raise SystemExit(
            f"the approval gate withheld {actual_withheld}, expected {expected_withheld}"
        )

    print()
    print("Next: PYTHONPATH=src uv run python -m examples.payments.charge_and_refund")


if __name__ == "__main__":
    main()
