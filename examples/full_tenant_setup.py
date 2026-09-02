from __future__ import annotations

import os
from typing import Final, Sequence
from uuid import uuid4

from examples.api import ApiClient, DemoState, ExpenseApiStub, mint_admin_token, require_id
from examples.api.provisioning import (
    KnowledgeDocument,
    ToolAliasCluster,
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
from examples.support import field, heading

BASE_URL: Final[str] = os.environ.get("AOC_BASE_URL", "http://127.0.0.1:8000")

AGENT_SYSTEM_PROMPT: Final[str] = (
    "You are an expense assistant for a company's employees. Work only from data present in "
    "the conversation and in the relevant history. Never invent an amount, a date or a "
    "merchant. Answer in English, in two or three sentences, in a professional and objective "
    "tone."
)

KNOWLEDGE_DOCUMENTS: Final[Sequence[KnowledgeDocument]] = (
    KnowledgeDocument(
        doc_type="identity_and_purpose",
        content=(
            "Identity: this assistant records and answers questions about corporate expenses "
            "over chat. It is the conversational front end for logging spending, checking what "
            "was already submitted and explaining the reimbursement rules. It does not replace "
            "an accountant and gives no tax advice. Tone of voice: professional, clear and "
            "direct."
        ),
        metadata={"topic": "identity", "audience": "employee"},
    ),
    KnowledgeDocument(
        doc_type="faq_recording_expenses",
        content=(
            "FAQ - recording expenses. Question: how do I record an expense? Answer: state the "
            "amount and what it was for, for example 'I spent 120 dollars at the supermarket'. "
            "Question: do I have to give the date? Answer: if you leave it out, today's date is "
            "used. Question: which payment methods can I log? Answer: credit card, debit card, "
            "bank transfer and cash."
        ),
        metadata={"topic": "faq", "audience": "employee"},
    ),
    KnowledgeDocument(
        doc_type="behaviour_and_limits",
        content=(
            "Behavioural principles: never invent financial data; work only with data available "
            "in the system; say explicitly when the information is missing; ask for "
            "confirmation whenever an ambiguity would change what gets recorded."
        ),
        metadata={"topic": "policy", "audience": "employee"},
    ),
)

TOOL_ALIAS_CLUSTERS: Final[Sequence[ToolAliasCluster]] = (
    ToolAliasCluster(
        operation_id="createExpense",
        cluster="direct_verbs",
        content=(
            "createExpense semantic aliases. Direct verbs for spending intent: I paid, I spent, "
            "I bought, I purchased, I settled, paid for, spent on, bought a, record an expense, "
            "log an expense, log spending, note down a purchase, add this expense, enter a "
            "receipt."
        ),
    ),
    ToolAliasCluster(
        operation_id="createExpense",
        cluster="payment_methods",
        content=(
            "createExpense semantic aliases. Payment method phrasing attached to recording an "
            "expense: paid by card, paid on credit, paid on debit, paid by bank transfer, paid "
            "in cash, put it on the company card, it came off the account, charged to the card, "
            "debit card, credit card, split into instalments."
        ),
    ),
    ToolAliasCluster(
        operation_id="createExpense",
        cluster="amount_signals",
        content=(
            "createExpense semantic aliases. Amount and total signals that indicate an expense "
            "statement: it came to, it was x dollars, it cost me, that was x, ended up at x, it "
            "set me back, spent x dollars, paid x dollars, a total of x dollars."
        ),
    ),
)


def stage_tenant(client: ApiClient, state: DemoState, suffix: str) -> None:
    heading("Tenant")
    tenant = client.post(
        "/core/v1/tenants",
        {
            "name": f"Expense Assistant {suffix}",
            "external_id": str(uuid4()),
            "description": "Tenant provisioned by examples/full_tenant_setup.py",
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
    agent = client.post("/core/v1/agents", {"name": "ExpenseAssistant"}, label="create agent")
    agent_id = require_id(agent, "id", "agent")
    version = client.post(
        f"/core/v1/agents/{agent_id}/versions",
        {
            "description": "Expense assistant v1",
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
            "name": "expense-assistant-flow",
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
            "title": "expense_context_default",
            "content": (
                "Prioritize objective guidance. If user intent is ambiguous, ask one direct "
                "clarification question."
            ),
            "created_by": "examples",
        },
        label="create user prompt",
    )
    return require_id(prompt, "id", "user prompt")


def main() -> None:
    print("Full tenant provisioning - the whole authoring surface, in the only order that works")
    print(f"api = {BASE_URL}")

    wait_seconds = int(os.environ.get("AOC_INGEST_WAIT_SECONDS", "45"))
    suffix = uuid4().hex[:8]
    state = DemoState()

    with ExpenseApiStub() as stub:
        field("upstream tool api", stub.base_url)
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
                client, state, openapi_url=stub.openapi_url, approved_operation_ids=None
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
            state.set("expense_api_base_url", stub.base_url)
            state.save()

    heading("Provisioned")
    field("tenant_id", state.get("tenant_id"))
    field("flow_id", state.get("flow_id"))
    field("agent_id", state.get("agent_id"))
    field("tool_config_id", state.get("tool_config_id"))
    field("state file", str(state.path))
    print()
    print("Next: PYTHONPATH=src uv run python -m examples.scenarios.run_conversation")


if __name__ == "__main__":
    main()
