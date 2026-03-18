from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
TENANT_ID = os.environ.get("TENANT_ID", "")
PRINCIPAL_ID = os.environ.get("PRINCIPAL_ID", "system")
CREATE_TENANT_ONLY = os.environ.get("CREATE_TENANT_ONLY", "").lower() in ("1", "true", "yes")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}


async def _post(client: httpx.AsyncClient, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    r = await client.post(f"{BASE_URL}{path}", json=body or {}, params=params, headers=_headers(), timeout=60.0)
    r.raise_for_status()
    return r.json() if r.content else {}


async def _get(client: httpx.AsyncClient, path: str) -> dict | list:
    r = client.get(f"{BASE_URL}{path}", headers=_headers(), timeout=30.0)
    r.raise_for_status()
    return r.json() if r.content else []


def _id(res: dict, key: str = "id") -> str:
    return str(res.get(key, res.get("id", "")))


async def create_tenant(client: httpx.AsyncClient) -> str:
    body = {
        "name": "Demo Tenant (API)",
        "timezone": "America/Sao_Paulo",
        "currency": "BRL",
        "language": "pt_BR",
        "is_active": True,
    }
    out = await _post(client, "/core/v1/tenants", body)
    return _id(out)


async def run_create_tenant_only(client: httpx.AsyncClient) -> None:
    tenant_id = await create_tenant(client)
    print(tenant_id)


def _demo_graph_definition(node_ids: list[str]) -> dict:
    n = node_ids
    if len(n) < 11:
        raise ValueError("need at least 11 node ids")
    mod, ctx, intent, clar_int, tool_sel, slot, clar_slot, tool_ex, err_h, fallback, resp = n[0], n[1], n[2], n[3], n[4], n[5], n[6], n[7], n[8], n[9], n[10]
    llm = lambda task, provider="OPENAI", model="gpt-4.1-mini", **kw: {"llm": {"task_type": task, "provider": provider, "model_alias": model, "temperature": 0.2, "top_p": 0.2, "use_system_prompt": True, "use_system_context": True, **kw}}
    return {
        "start_node": mod,
        "nodes": {
            mod: {"type": "InputModerationNode", "config": {"primary": {"provider": "SLM_LOCAL", "model_alias": "slm-local-moderation", "timeout_ms": 300}, "fallback_enabled": True, "prompt_key": "InputModerationNode", "temperature": 0.0, "max_tokens": 18}},
            ctx: {"type": "UserContextEnrichmentNode", "config": {"publish": True, "layers": {"allow_tenant_knowledge": True, "allow_user_memory_structured": True, "allow_user_memory_vector": True}}},
            intent: {"type": "IntentDetectionNode", "config": llm("INTENT_SELECTION", temperature=0, top_p=0.05, use_system_prompt=False, use_conversation_history=False)},
            tool_sel: {"type": "ToolSelectionNode", "config": llm("TOOL_SELECTION", temperature=0, top_p=0.1, use_system_prompt=False, use_conversation_history=False)},
            slot: {"type": "ParamExtractionNode", "config": llm("SLOT_FILLING", temperature=0.2, top_p=0.2, use_system_prompt=False, use_conversation_history=True)},
            clar_int: {"type": "ClarificationNode", "config": {"resume_to_node_id": intent, **llm("CLARIFICATION", model="gpt-4o", temperature=0.3, top_p=0.4, use_conversation_history=True)}},
            clar_slot: {"type": "ClarificationNode", "config": {"resume_to_node_id": slot, **llm("CLARIFICATION", model="gpt-4o", temperature=0.3, top_p=0.4, use_conversation_history=True)}},
            tool_ex: {"type": "ToolExecutionNode", "config": {}},
            err_h: {"type": "ToolErrorHandlerNode", "config": {"max_retries": 1}},
            fallback: {"type": "FallbackNodeSLA", "config": llm("FALLBACK_SLA", use_system_prompt=False, use_system_context=False, temperature=0.0, top_p=0.0, use_conversation_history=False)},
            resp: {"type": "ResponseComposer", "config": llm("RESPONSE_RENDER", model="gpt-4o", temperature=0.3, top_p=0.4, use_conversation_history=True)},
        },
        "edges": [
            {"from_node": mod, "to_node": ctx, "condition": "flagged == false", "edge_kind": "NORMAL"},
            {"from_node": mod, "to_node": fallback, "condition": "flagged == true", "edge_kind": "NORMAL"},
            {"from_node": ctx, "to_node": intent, "condition": "1==1", "edge_kind": "NORMAL"},
            {"from_node": intent, "to_node": clar_int, "condition": "overall_confidence < 0.6", "edge_kind": "NORMAL"},
            {"from_node": intent, "to_node": tool_sel, "condition": "HasAny(result.intent_type, ['command']) and overall_confidence >= 0.8", "edge_kind": "NORMAL"},
            {"from_node": intent, "to_node": resp, "condition": "overall_confidence >= 0.6 and (HasAny(result.intent_type, ['conversation']) or not HasAny(result.intent_type, ['command']))", "edge_kind": "NORMAL"},
            {"from_node": clar_int, "to_node": resp, "condition": "1==1", "edge_kind": "NORMAL"},
            {"from_node": tool_sel, "to_node": slot, "condition": "len(result) >= 1", "edge_kind": "NORMAL"},
            {"from_node": slot, "to_node": clar_slot, "condition": "HasAny(result.status, ['incomplete'])", "edge_kind": "NORMAL"},
            {"from_node": clar_slot, "to_node": slot, "condition": "1==1", "edge_kind": "LOOP"},
            {"from_node": slot, "to_node": tool_ex, "condition": "HasAll(result.status, ['ready'])", "edge_kind": "NORMAL"},
            {"from_node": tool_ex, "to_node": resp, "condition": "HasAll(result.status, ['success', 'scheduled'])", "edge_kind": "NORMAL"},
            {"from_node": tool_ex, "to_node": err_h, "condition": "HasAny(result.status, ['incomplete', 'error', 'cancelled'])", "edge_kind": "NORMAL"},
            {"from_node": err_h, "to_node": tool_ex, "condition": "retry_operation_ids_count > 0", "edge_kind": "LOOP"},
            {"from_node": err_h, "to_node": fallback, "condition": "fallback_required == true", "edge_kind": "NORMAL"},
            {"from_node": err_h, "to_node": resp, "condition": "retry_operation_ids_count == 0 and fallback_required == false", "edge_kind": "NORMAL"},
            {"from_node": fallback, "to_node": resp, "condition": "1==1", "edge_kind": "NORMAL"},
        ],
    }


async def run_full_rebuild(client: httpx.AsyncClient, tenant_id: str) -> None:
    if not AUTH_TOKEN or not tenant_id:
        raise SystemExit("AUTH_TOKEN and TENANT_ID are required for full rebuild")

    ai_task_ids: list[str] = []
    for _ in range(4):
        out = await _post(client, "/core/v1/ai-tasks", {"name": "demo-task"})
        ai_task_ids.append(_id(out))

    out = await _post(client, "/core/v1/models", {"name": "demo-model", "provider": "OPENAI", "model_alias": "gpt-4.1-mini"})
    model_id = _id(out)

    out = await _post(client, "/core/v1/ai-execution-policies", {"name": "demo-policy"})
    policy_id = _id(out)
    out = await _post(client, "/core/v1/ai-execution-policy-versions", {"ai_execution_policy_id": policy_id, "model_id": model_id})
    ver_id = _id(out)
    await _post(client, f"/core/v1/ai-execution-policies/{policy_id}/versions/{ver_id}:publish", {"change_type": "UPDATE", "justification": "rebuild-via-api"})

    openapi_url = os.environ.get("OPENAPI_URL", "")
    tool_config_id = None
    if openapi_url:
        await _post(client, "/core/v1/tools/import-tools", {"openapi_url": openapi_url})
        configs = await _get(client, "/core/v1/tool-configs")
        if isinstance(configs, list) and configs:
            tool_config_id = _id(configs[0])

    out = await _post(client, "/core/v1/agents", {"name": "Demo Agent (API)"})
    agent_id = _id(out)
    out = await _post(client, f"/core/v1/agents/{agent_id}/versions", {})
    agent_version_id = _id(out)
    await _post(client, f"/core/v1/agents/{agent_id}/versions/{agent_version_id}:publish", {})
    if tool_config_id:
        await _post(client, "/core/v1/agent-version-tool-bindings", {"agent_version_id": agent_version_id, "tool_config_id": tool_config_id})

    out = await _post(client, "/core/v1/flows", {"name": "Demo Flow (API)", "description": "Rebuilt via API"})
    flow_id = _id(out)
    out = await _post(client, f"/core/v1/flows/{flow_id}/versions", {})
    flow_version_id = _id(out)

    node_order = [
        None,
        None,
        ai_task_ids[0] if len(ai_task_ids) > 0 else None,
        ai_task_ids[2] if len(ai_task_ids) > 2 else None,
        None,
        ai_task_ids[1] if len(ai_task_ids) > 1 else None,
        None,
        None,
        None,
        ai_task_ids[2] if len(ai_task_ids) > 2 else None,
        ai_task_ids[3] if len(ai_task_ids) > 3 else None,
    ]
    node_ids: list[str] = []
    for ai_task_id in node_order:
        body = {"flow_version_id": flow_version_id}
        if ai_task_id:
            body["ai_task_id"] = ai_task_id
        out = await _post(client, "/core/v1/nodes", body)
        node_ids.append(_id(out))

    prompt_templates = [
        ("InputModerationNode", "Return JSON only. {\"flagged\": boolean}"),
        ("IntentDetectionNode", "# Task\nClassify all user intents types and confidence."),
        ("ParamExtractionNode", "# Task\nExtract parameters from user input."),
        ("ResponseComposer", "# Task\nFormat response for the user."),
        ("ClarificationNode", "# Task\nAsk the user for missing required information."),
        ("ToolSelectionNode", "# Task\nSelect the best matching tool(s) for each user intent."),
        ("FallbackNodeSLA", "Classify the user message. Reply in JSON with system_output and new_priority."),
    ]
    for node_type, template in prompt_templates:
        await _post(client, f"/core/v1/nodes/{node_type}/prompt", {"node_type": node_type, "template_text": template, "output_schema": {"type": "object"}})

    for node_id in node_ids[:8]:
        await _post(client, "/core/v1/node-agent-bindings", {"node_id": node_id, "agent_version_id": agent_version_id})
    if len(node_ids) > 9:
        await _post(client, "/core/v1/node-agent-bindings", {"node_id": node_ids[9], "agent_version_id": agent_version_id})

    definition = _demo_graph_definition(node_ids)
    await _post(client, f"/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:draft", {"flow_id": flow_id, "flow_version_id": flow_version_id, "definition": definition, "principal_id": PRINCIPAL_ID})
    await _post(client, f"/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:validate", {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": PRINCIPAL_ID})
    change = {"change_type": "UPDATE", "justification": "rebuild-via-api"}
    await _post(client, f"/core/v1/flows/{flow_id}/versions/{flow_version_id}:publish", change)
    await _post(client, f"/core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:compile", {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": PRINCIPAL_ID})
    await _post(client, f"/core/v1/flows/{flow_id}/versions/{flow_version_id}:activate", change)

    out = await _post(client, "/core/v1/runtime-policies", {"scope": "flow", "flow_id": flow_id, "version": "1", "policy_definition": {}})
    runtime_id = _id(out)
    await _post(client, f"/core/v1/runtime-policies/{runtime_id}:activate", {"change_type": "UPDATE", "justification": "rebuild-via-api"})

    out = await _post(client, "/core/v1/access-policies", {"name": "demo-access"})
    ap_id = _id(out)
    out = await _post(client, f"/core/v1/access-policies/{ap_id}/versions", {})
    ap_ver_id = _id(out)
    await _post(client, f"/core/v1/access-policies/versions/{ap_ver_id}:publish", {})

    out = await _post(client, "/core/v1/rate-limit-policies", {"name": "demo-rate-limit"})
    rl_id = _id(out)
    out = await _post(client, f"/core/v1/rate-limit-policies/{rl_id}/versions", {})
    rl_ver_id = _id(out)
    await _post(client, f"/core/v1/rate-limit-policies/versions/{rl_ver_id}:publish", {})

    out = await _post(client, "/core/v1/billing-policies", {"name": "demo-billing"})
    bp_id = _id(out)
    out = await _post(client, f"/core/v1/billing-policies/{bp_id}/versions", {})
    bp_ver_id = _id(out)
    await _post(client, f"/core/v1/billing-policies/versions/{bp_ver_id}:publish", {})
    await _post(client, f"/core/v1/billing-policies/versions/{bp_ver_id}:activate", {})

    out = await _post(client, "/core/v1/memory-policies", {"name": "demo-memory"})
    mp_id = _id(out)
    out = await _post(client, f"/core/v1/memory-policies/{mp_id}/versions", {})
    mp_ver_id = _id(out)
    await _post(client, f"/core/v1/memory-policies/versions/{mp_ver_id}:publish", {})
    await _post(client, f"/core/v1/memory-policies/versions/{mp_ver_id}:activate", {})

    out = await _post(client, "/core/v1/rag-policies", {"name": "demo-rag"})
    rp_id = _id(out)
    out = await _post(client, f"/core/v1/rag-policies/{rp_id}/versions", {})
    rp_ver_id = _id(out)
    await _post(client, f"/core/v1/rag-policies/versions/{rp_ver_id}:publish", {})
    await _post(client, f"/core/v1/rag-policies/versions/{rp_ver_id}:activate", {})

    for i, node_id in enumerate(node_ids[:5]):
        if i < len(ai_task_ids) and policy_id and ver_id:
            await _post(client, "/core/v1/node-ai-execution-policy-bindings", {"node_id": node_id, "ai_execution_policy_version_id": ver_id})

    await _post(client, "/admin/llm/provider", params={"tenant_id": tenant_id, "provider": "OPENAI", "status": "ACTIVE"})
    await _post(client, "/admin/llm/model-mapping", params={"tenant_id": tenant_id, "provider": "OPENAI", "model_alias": "gpt-4.1-mini", "provider_model": "gpt-4.1-mini"})
    await _post(client, "/admin/llm/pricing", params={"provider": "OPENAI", "provider_model": "gpt-4.1-mini", "unit": "TOKEN", "input_cost_per_1k": 0.0, "output_cost_per_1k": 0.0})

    print("ok", "flow_id", flow_id, "agent_id", agent_id, "tenant_id", tenant_id)


async def main() -> None:
    if not AUTH_TOKEN:
        raise SystemExit("AUTH_TOKEN is required")

    async with httpx.AsyncClient() as client:
        if CREATE_TENANT_ONLY:
            await run_create_tenant_only(client)
            return
        if not TENANT_ID:
            raise SystemExit("TENANT_ID is required for full rebuild (or set CREATE_TENANT_ONLY=1 to only create tenant)")
        await run_full_rebuild(client, TENANT_ID)


if __name__ == "__main__":
    asyncio.run(main())
