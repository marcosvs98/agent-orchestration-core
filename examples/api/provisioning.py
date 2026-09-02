from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Final, List, NamedTuple, Optional, Sequence, Tuple

from examples.api.client import ApiClient, require_id
from examples.api.state import DemoState
from examples.support import field, heading

PROMPTS_FILE: Final[Path] = Path(__file__).resolve().parent / "node_prompts.json"

CHAT_MODEL_ALIAS: Final[str] = "gpt-4o"
FAST_MODEL_ALIAS: Final[str] = "gpt-4.1-mini"
MODERATION_MODEL_ALIAS: Final[str] = "omni-moderation-latest"
EMBED_RETRIEVAL_ALIAS: Final[str] = "text-embedding-3-small"
EMBED_INDEXING_ALIAS: Final[str] = "text-embedding-3-large"

EMBED_RETRIEVAL_DIMENSION: Final[int] = 1536
EMBED_INDEXING_DIMENSION: Final[int] = 3072

RETRIEVAL_SIMILARITY_THRESHOLD: Final[float] = 0.25

MODEL_CATALOG: Final[Sequence[Tuple[str, str]]] = (
    (CHAT_MODEL_ALIAS, "LLM"),
    ("gpt-4o-mini", "LLM"),
    (FAST_MODEL_ALIAS, "LLM"),
    (MODERATION_MODEL_ALIAS, "LLM"),
    (EMBED_RETRIEVAL_ALIAS, "EMBEDDING"),
    (EMBED_INDEXING_ALIAS, "EMBEDDING"),
)

ALLOWED_ACTIONS: Final[Sequence[str]] = (
    "conversation:turn:create",
    "execution:flow_run:create",
    "execution:flow_run:get",
    "execution:flow_run:resume",
    "execution:tool_run:create",
    "execution:tool_run:execute",
    "execution:events:list",
    "execution:graph_state:get",
    "execution:node_runs:list",
    "execution:agent_runs:list",
)

GRAPH_NODE_TYPES: Final[Sequence[str]] = (
    "ContentModeration",
    "ToolResolver",
    "ToolInputFiller",
    "QueryClarifier",
    "ToolExecutor",
    "ToolErrorHandlerNode",
    "HumanFallback",
    "MemoryCommitNode",
    "ResponseBuilder",
)

MEMORY_SCHEMA_ID: Final[str] = "user.preference.v1"


class KnowledgeDocument(NamedTuple):
    doc_type: str
    content: str
    metadata: Dict[str, str]


class ToolAliasCluster(NamedTuple):
    operation_id: str
    cluster: str
    content: str


class ImportedTool(NamedTuple):
    operation_id: str
    tool_id: str
    tool_config_id: str
    method: str
    path: str
    summary: str
    required_fields: Sequence[str]
    approved: bool


def make_llm_config(
    task_type: str, model_alias: str, temperature: float, top_p: float
) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "provider": "OPENAI",
        "model_alias": model_alias,
        "temperature": temperature,
        "top_p": top_p,
        "use_system_prompt": True,
        "use_system_context": True,
        "max_tokens": None,
        "completion_budget": {"schema_factor": 1.5, "safety_margin": 24.0, "floor": 64.0},
        "use_conversation_history": True,
    }


def build_graph_definition(
    nodes: Dict[str, str],
    rag_config_id: str,
    tool_executor_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    moderation = nodes["ContentModeration"]
    resolver = nodes["ToolResolver"]
    filler = nodes["ToolInputFiller"]
    clarifier = nodes["QueryClarifier"]
    executor = nodes["ToolExecutor"]
    error_handler = nodes["ToolErrorHandlerNode"]
    fallback = nodes["HumanFallback"]
    memory = nodes["MemoryCommitNode"]
    response = nodes["ResponseBuilder"]

    return {
        "start_node": moderation,
        "nodes": {
            moderation: {
                "type": "ContentModeration",
                "config": {
                    "primary": {
                        "provider": "OPENAI",
                        "model_alias": MODERATION_MODEL_ALIAS,
                        "timeout_ms": 3000,
                    },
                    "fallback_enabled": False,
                    "prompt_key": "ContentModeration",
                    "temperature": 0.0,
                    "max_tokens": 18,
                },
            },
            resolver: {
                "type": "ToolResolver",
                "config": {
                    "llm": make_llm_config("TOOL_SELECTION", FAST_MODEL_ALIAS, 0.0, 0.1),
                    "confidence_threshold": 0.5,
                    "top_k": 10,
                },
            },
            filler: {
                "type": "ToolInputFiller",
                "config": {"llm": make_llm_config("SLOT_FILLING", FAST_MODEL_ALIAS, 0.2, 0.2)},
            },
            clarifier: {
                "type": "QueryClarifier",
                "config": {
                    "resume_to_node_id": filler,
                    "llm": make_llm_config("CLARIFICATION", CHAT_MODEL_ALIAS, 0.3, 0.4),
                },
            },
            executor: {"type": "ToolExecutor", "config": tool_executor_config or {}},
            error_handler: {"type": "ToolErrorHandlerNode", "config": {"max_retries": 1}},
            fallback: {
                "type": "HumanFallback",
                "config": {"llm": make_llm_config("FALLBACK_SLA", FAST_MODEL_ALIAS, 0.0, 0.0)},
            },
            memory: {
                "type": "MemoryCommitNode",
                "config": {
                    "schema_id": MEMORY_SCHEMA_ID,
                    "schema_version": 1,
                    "source": "explicit_user",
                    "rag_config_id": rag_config_id,
                    "data": {
                        "preference_key": "examples.memory_commit",
                        "preference_value": "graph_seed",
                    },
                    "data_merge": [
                        {
                            "from_node_id": filler,
                            "path": "result.0.params.description",
                            "target_key": "last_tool_description",
                        }
                    ],
                },
            },
            response: {
                "type": "ResponseBuilder",
                "config": {"llm": make_llm_config("RESPONSE_RENDER", CHAT_MODEL_ALIAS, 0.3, 0.4)},
            },
        },
        "edges": [
            {"from_node": moderation, "to_node": resolver, "condition": "flagged == false"},
            {"from_node": moderation, "to_node": fallback, "condition": "flagged == true"},
            {"from_node": resolver, "to_node": filler, "condition": "len(result) >= 1"},
            {"from_node": resolver, "to_node": memory, "condition": "len(result) < 1"},
            {
                "from_node": filler,
                "to_node": clarifier,
                "condition": "HasAny(result.status, ['incomplete'])",
            },
            {
                "from_node": clarifier,
                "to_node": filler,
                "condition": "1==1",
                "edge_kind": "LOOP",
            },
            {
                "from_node": filler,
                "to_node": executor,
                "condition": "HasAll(result.status, ['ready'])",
            },
            {
                "from_node": executor,
                "to_node": response,
                "condition": "HasAll(result.status, ['success', 'scheduled'])",
            },
            {
                "from_node": executor,
                "to_node": error_handler,
                "condition": "HasAny(result.status, ['incomplete', 'error', 'cancelled'])",
            },
            {
                "from_node": error_handler,
                "to_node": executor,
                "condition": "retry_operation_ids_count > 0",
                "edge_kind": "LOOP",
            },
            {
                "from_node": error_handler,
                "to_node": fallback,
                "condition": "fallback_required == true",
            },
            {
                "from_node": error_handler,
                "to_node": memory,
                "condition": "retry_operation_ids_count == 0 and fallback_required == false",
            },
            {"from_node": fallback, "to_node": memory, "condition": "1==1"},
            {"from_node": memory, "to_node": response, "condition": "1==1"},
        ],
    }


def stage_tenant_token(client: ApiClient, state: DemoState) -> None:
    heading("Tenant token")
    token = client.post(
        "/core/v1/auth/tenant-token",
        {"tenant_id": state.get("tenant_id")},
        label="issue tenant token",
    )
    access_token = require_id(token, "access_token", "issue tenant token")
    client.set_token(access_token)
    state.set("tenant_token", access_token)
    field("token", access_token[:24] + "...")
    current = client.get("/core/v1/tenants/current", label="verify tenant scope")
    field("scoped to", current.get("name"))


def stage_models(client: ApiClient, state: DemoState) -> None:
    heading("Model catalog")
    print("  The catalog is GLOBAL and model.name is unique, and llm model mappings are")
    print("  resolved by `Model.name == model_alias`. So names must be the aliases the")
    print("  graph uses, and an existing row must be reused rather than recreated.")

    existing = client.get("/core/v1/models", label="list model catalog")
    by_name = {m["name"]: m["id"] for m in existing if isinstance(m, dict)}

    ids: Dict[str, str] = {}
    for name, model_type in MODEL_CATALOG:
        if name in by_name:
            ids[name] = by_name[name]
            continue
        created = client.post(
            "/core/v1/models",
            {"name": name, "provider": "OPENAI", "type": model_type},
            label=f"create model {name}",
        )
        ids[name] = require_id(created, "id", f"model {name}")

    state.set("model_ids", ids)
    state.set("model_chat_id", ids[CHAT_MODEL_ALIAS])
    state.set("model_embed_retrieval_id", ids[EMBED_RETRIEVAL_ALIAS])
    state.set("model_embed_indexing_id", ids[EMBED_INDEXING_ALIAS])
    field("models available", len(ids))


def stage_llm_provider(client: ApiClient, state: DemoState) -> None:
    heading("LLM provider, model mappings and pricing")
    tenant_id = state.get("tenant_id")

    client.post(
        "/admin/llm/provider",
        params={
            "tenant_id": tenant_id,
            "provider": "OPENAI",
            "status": "ACTIVE",
            "credential_secret_ref": "env:openai_api_key",
        },
        label="upsert provider config",
    )
    for alias, _ in MODEL_CATALOG:
        client.post(
            "/admin/llm/model-mapping",
            params={
                "tenant_id": tenant_id,
                "provider": "OPENAI",
                "model_alias": alias,
                "provider_model": alias,
                "status": "ACTIVE",
            },
            label=f"map alias {alias}",
        )
        client.post(
            "/admin/llm/pricing",
            params={
                "provider": "OPENAI",
                "provider_model": alias,
                "unit": "TOKENS_1K",
                "input_cost_per_1k": 0.005,
                "output_cost_per_1k": 0.015,
                "currency": "USD",
                "status": "ACTIVE",
            },
            label=f"price {alias}",
        )
    print("  note: without an ACTIVE provider config every LLM node fails the run with")
    print("        STRUCTURAL_ERROR / llm_provider_not_active. These /admin/llm routes take")
    print("        QUERY parameters, not a JSON body, and read tenant_id from the query")
    print("        string rather than the JWT.")


def stage_ai_policy(client: ApiClient, state: DemoState) -> None:
    heading("AI execution policy")
    policy = client.post(
        "/core/v1/ai-execution-policies",
        {"description": "AI execution policy for the examples tenant"},
        label="create ai execution policy",
    )
    policy_id = require_id(policy, "id", "ai execution policy")
    version = client.post(
        "/core/v1/ai-execution-policy-versions",
        {
            "ai_execution_policy_id": policy_id,
            "model_id": state.get("model_chat_id"),
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
        },
        label="create policy version",
    )
    version_id = require_id(version, "id", "ai execution policy version")
    client.post(
        f"/core/v1/ai-execution-policies/{policy_id}/versions/{version_id}:validate",
        label="validate policy version",
    )
    client.post(
        f"/core/v1/ai-execution-policies/{policy_id}/versions/{version_id}:publish",
        {"change_type": "PUBLISH", "justification": "examples bootstrap"},
        label="publish policy version",
    )
    state.set("ai_execution_policy_id", policy_id)
    state.set("ai_execution_policy_version_id", version_id)


def stage_rag(client: ApiClient, state: DemoState, suffix: str) -> None:
    heading("RAG: vector store, chunking rule, config")
    store = client.post(
        "/core/v1/vector-stores",
        {
            "name": f"examples-knowledge-{suffix}",
            "embedding_model": EMBED_INDEXING_ALIAS,
            "embedding_dimension": EMBED_INDEXING_DIMENSION,
        },
        label="create vector store",
    )
    store_id = require_id(store, "id", "vector store")

    rule = client.post(
        "/core/v1/rag-chunking-rules",
        {
            "name": f"examples-token-window-{suffix}",
            "status": "ACTIVE",
            "strategy": "TOKEN_WINDOW",
            "params": {
                "strategy": "TOKEN_WINDOW",
                "target_tokens": 500,
                "overlap_tokens": 50,
                "max_chunks_per_document": 100,
                "max_document_chars": 100000,
            },
        },
        label="create chunking rule",
    )
    rule_id = require_id(rule, "id", "chunking rule")

    config = client.post(
        "/core/v1/rag-configs",
        {
            "vector_store_id": store_id,
            "chunking_rule_id": rule_id,
            "corpus_kind": "TENANT_KNOWLEDGE",
            "options": {
                "embedding": {
                    "model_id": state.get("model_embed_retrieval_id"),
                    "provider": "OPENAI",
                    "dimension": EMBED_RETRIEVAL_DIMENSION,
                    "model_alias": EMBED_RETRIEVAL_ALIAS,
                },
                "retrieval": {
                    "top_k": 5,
                    "filters": None,
                    "similarity_threshold": RETRIEVAL_SIMILARITY_THRESHOLD,
                },
                "indexing_embedding": {
                    "model_id": state.get("model_embed_indexing_id"),
                    "provider": "OPENAI",
                    "dimension": EMBED_INDEXING_DIMENSION,
                    "model_alias": EMBED_INDEXING_ALIAS,
                },
                "generation_contract": {"allow_extrapolation": False},
            },
        },
        label="create rag config",
    )
    state.set("vector_store_id", store_id)
    state.set("chunking_rule_id", rule_id)
    state.set("rag_config_id", require_id(config, "id", "rag config"))
    print(f"  retrieval.similarity_threshold is {RETRIEVAL_SIMILARITY_THRESHOLD}, not the 0.5 that")
    print("  reads like a safe default. ToolCatalogRetriever applies")
    print("  min(config threshold, 0.42), and text-embedding-3-large scores a correct but")
    print("  loosely worded match around 0.32 - 'how much money do we have' against the")
    print("  balance aliases scores 0.32, while 'refund 15.00 of payment X' scores 0.53. At")
    print("  0.5 the loose half of the intent space silently retrieves nothing and the")
    print("  resolver returns [] without ever calling the LLM.")
    print("  Note the pair: documents are embedded with indexing_embedding")
    print("  (text-embedding-3-large, 3072) and queries with the SAME model truncated to")
    print("  embedding.dimension (1536). Setting embedding to a different model family")
    print("  would compare incompatible vector spaces and score everything near 0.05.")


def stage_publish_rag(client: ApiClient, state: DemoState) -> None:
    heading("Validate and publish the RAG config")
    rag_config_id = state.get("rag_config_id")
    validated = client.post(
        f"/core/v1/rag-configs/{rag_config_id}:validate",
        label="validate rag config",
    )
    field("status", validated.get("status") if isinstance(validated, dict) else validated)
    client.post(
        f"/core/v1/rag-configs/{rag_config_id}:publish",
        {"change_type": "PUBLISH", "justification": "examples bootstrap"},
        label="publish rag config",
    )
    print("  The RAG config is published BEFORE the tools are imported on purpose. ToolsService")
    print("  wants to write a catalog document per imported operation into the tenant's newest")
    print("  PUBLISHED rag config, and indexes nothing when there is none.")
    print("  In this build that write never happens anyway: containers.py constructs ToolsService")
    print("  without tool_catalog_indexer, so the parameter defaults to None and the call returns")
    print("  early. The catalog documents this tenant retrieves on are the ones ingested below.")


def stage_import_and_approve_tools(
    client: ApiClient,
    state: DemoState,
    *,
    openapi_url: str,
    approved_operation_ids: Optional[Sequence[str]] = None,
) -> List[ImportedTool]:
    heading("Import tools from OpenAPI, then approve them")
    field("openapi_url", openapi_url)

    imported = client.post(
        "/core/v1/tools/import-tools",
        {"openapi_url": openapi_url},
        label="import tools",
    )
    tools = imported.get("tools") if isinstance(imported, dict) else None
    if not isinstance(tools, list) or not tools:
        raise SystemExit(f"import-tools returned no tools: {json.dumps(imported)[:400]}")
    field("operations imported", imported.get("imported_count"))

    print("  import-tools returns `tools: list[Tool]`, so tools[N].id is a TOOL id, not a")
    print("  tool_config id. Binding a tool id to an agent version fails with")
    print("  404 tool_config_not_found; the real config comes from GET /tool-configs.")

    tool_ids = {require_id(tool, "id", "imported tool") for tool in tools}
    configs = client.get(
        "/core/v1/tool-configs",
        params={"limit": 200},
        label="list tool configs",
    )
    if not isinstance(configs, list):
        raise SystemExit("GET /tool-configs did not return a list")

    newest_by_tool: Dict[str, Dict[str, Any]] = {}
    for config in configs:
        tool_id = str(config.get("tool_id"))
        if tool_id not in tool_ids:
            continue
        current = newest_by_tool.get(tool_id)
        if current is None or _version_tuple(config) > _version_tuple(current):
            newest_by_tool[tool_id] = config
    if not newest_by_tool:
        raise SystemExit(f"no tool_config found for the imported tools {sorted(tool_ids)}")

    reviewed: List[ImportedTool] = []
    for tool_id, config in newest_by_tool.items():
        payload = config.get("config") or {}
        request_schema = payload.get("request_schema") or {}
        operation_id = str(payload.get("operation_id") or "")
        reviewed.append(
            ImportedTool(
                operation_id=operation_id,
                tool_id=tool_id,
                tool_config_id=require_id(config, "id", "tool config"),
                method=str(payload.get("method") or ""),
                path=str(payload.get("path") or ""),
                summary=str(payload.get("summary") or ""),
                required_fields=tuple(request_schema.get("required") or ()),
                approved=(approved_operation_ids is None or operation_id in approved_operation_ids),
            )
        )
    reviewed.sort(key=lambda tool: tool.operation_id)

    print()
    print("  review the imported catalog before anything is exposed to an agent")
    print(f"    {'operation_id':<28} {'method':<7} {'path':<26} required")
    for tool in reviewed:
        required = ",".join(tool.required_fields) or "-"
        print(f"    {tool.operation_id:<28} {tool.method:<7} {tool.path:<26} {required[:40]}")
    print()

    approved_ids: List[str] = []
    for tool in reviewed:
        if tool.approved:
            client.post(
                f"/core/v1/tool-configs/{tool.tool_config_id}:publish",
                {"change_type": "PUBLISH", "justification": "approved for this tenant"},
                label=f"approve {tool.operation_id}",
            )
            approved_ids.append(tool.tool_config_id)
        else:
            client.post(
                f"/core/v1/tool-configs/{tool.tool_config_id}:disable",
                label=f"withhold {tool.operation_id}",
            )

    print("  note: import-tools already publishes every config it creates, so :publish here is")
    print("        an idempotent no-op that records the approval as an authoring event. The")
    print("        withheld half is the part that actually changes state - :disable takes a")
    print("        config out of PUBLISHED, and the tool catalog retriever only hydrates")
    print("        PUBLISHED configs, so a disabled operation can never be selected.")

    state.set("tool_ids", sorted(tool_ids))
    state.set("tool_config_ids", approved_ids)
    state.set("tool_config_id", approved_ids[0] if approved_ids else None)
    state.set("approved_operation_ids", [t.operation_id for t in reviewed if t.approved])
    state.set("withheld_operation_ids", [t.operation_id for t in reviewed if not t.approved])
    field("approved", f"{len(approved_ids)}/{len(reviewed)}")
    return reviewed


def _version_tuple(config: Dict[str, Any]) -> Tuple[int, int, int]:
    return (
        int(config.get("version_major") or 0),
        int(config.get("version_minor") or 0),
        int(config.get("version_patch") or 0),
    )


def stage_ingest(
    client: ApiClient,
    state: DemoState,
    *,
    knowledge_documents: Sequence[KnowledgeDocument],
    tool_aliases: Sequence[ToolAliasCluster],
    imported_tools: Sequence[ImportedTool],
    wait_seconds: int,
) -> None:
    heading("Ingest tenant knowledge and tool aliases")
    rag_config_id = state.get("rag_config_id")
    source = f"examples-{state.get('tenant_id')}"

    documents: List[Dict[str, Any]] = [
        {
            "source": source,
            "doc_type": document.doc_type,
            "content": document.content,
            "version": "1",
            "metadata": dict(document.metadata),
        }
        for document in knowledge_documents
    ]

    by_operation = {tool.operation_id: tool for tool in imported_tools}
    covered = {alias.operation_id for alias in tool_aliases} & set(by_operation)
    uncovered = sorted(
        tool.operation_id
        for tool in imported_tools
        if tool.approved and tool.operation_id not in covered
    )
    if uncovered:
        raise SystemExit(
            f"approved operations with no tool_catalog document would be unreachable: {uncovered}"
        )

    for alias in tool_aliases:
        tool = by_operation.get(alias.operation_id)
        if tool is None:
            continue
        documents.append(
            {
                "source": "tool_catalog",
                "doc_type": "tool_catalog",
                "content": alias.content,
                "version": f"{alias.operation_id}.v1.alias.{alias.cluster}",
                "metadata": {
                    "category": "TOOL_CATALOG",
                    "tool_id": tool.tool_id,
                    "tool_config_id": tool.tool_config_id,
                    "tool_name": tool.operation_id,
                    "operation_id": tool.operation_id,
                    "method": tool.method,
                    "path": tool.path,
                    "cluster": alias.cluster,
                    "tool_intent": "query" if tool.method == "GET" else "command",
                },
            }
        )

    print("  ToolResolver does not read the agent's tool bindings to find candidates: it runs a")
    print("  vector search over documents whose source and doc_type are 'tool_catalog' and whose")
    print("  metadata carries a real tool_config_id, and only then intersects with the bindings.")
    print("  Every approved operation therefore needs at least one catalog document here, phrased")
    print("  the way a person actually asks, or it is retrievable by nobody.")
    print("  The withheld operations get catalog documents too, deliberately. That is the only")
    print("  way the approval gate is actually exercised: their documents come back as vector")
    print("  hits and are then dropped because hydration keeps PUBLISHED configs only. Skipping")
    print("  them would make the gate look effective when nothing had tested it.")

    accepted = client.post(
        f"/core/v1/rag-configs/{rag_config_id}/documents:ingest",
        documents,
        label=f"ingest {len(documents)} documents",
    )
    field("job_id", accepted.get("job_id"))
    field("accepted_count", accepted.get("accepted_count"))
    print(
        "  note: ingest returns 202 immediately and embeds in a background task whose\n"
        "        exceptions are swallowed - the only honest check is to poll the documents."
    )

    expected = len(documents)
    deadline = time.time() + wait_seconds
    stored: List[Dict[str, Any]] = []
    while time.time() < deadline:
        stored = client.get(
            "/core/v1/rag-documents",
            params={"rag_config_id": rag_config_id, "limit": 400},
            label="poll ingested documents",
        )
        if isinstance(stored, list) and len(stored) >= expected:
            break
        time.sleep(3)

    count = len(stored) if isinstance(stored, list) else 0
    field("documents stored", f"{count}/{expected}")
    if count < expected:
        print(
            "  WARNING: not every document landed. Embedding needs a working OPENAI_API_KEY;\n"
            "           the flow still runs, but retrieval will be thin."
        )
    state.set("rag_documents_ingested", count)


def stage_prompts(client: ApiClient, state: DemoState) -> None:
    heading("Node prompts")
    prompts = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    prompt_ids: Dict[str, str] = {}
    for prompt in prompts:
        node_type = prompt["node_type"]
        created = client.post(
            f"/core/v1/nodes/{node_type}/prompt",
            prompt,
            label=f"prompt {node_type}",
        )
        prompt_ids[node_type] = require_id(created, "prompt_id", f"prompt {node_type}")
    state.set("node_prompt_ids", prompt_ids)
    field("prompts created", len(prompt_ids))
    print("  note: node prompts are keyed by node_type in a GLOBAL, non-tenant-scoped table.")


def stage_nodes(client: ApiClient, state: DemoState) -> None:
    heading("Nodes")
    print("  Graph node ids must be real `node` rows: node_step_runner creates every NodeRun")
    print("  with node_id=UUID(current_node_id), and node_run.node_id is a RESTRICT foreign key.")
    flow_id = state.get("flow_id")
    flow_version_id = state.get("flow_version_id")
    prompt_ids = state.get("node_prompt_ids")
    rag_config_id = state.get("rag_config_id")

    nodes: Dict[str, str] = {}
    for node_type in GRAPH_NODE_TYPES:
        body: Dict[str, Any] = {
            "flow_id": flow_id,
            "flow_version_id": flow_version_id,
            "node_type": node_type,
            "node_prompt_id": prompt_ids[node_type],
            "allow_rag_tenant": True,
            "allow_session_context": True,
            "rag_config_id": rag_config_id,
        }
        if node_type == "MemoryCommitNode":
            body["allow_memory_write"] = True
            body["allow_user_memory_structured"] = True
            body["config"] = {
                "schema_id": MEMORY_SCHEMA_ID,
                "schema_version": 1,
                "source": "explicit_user",
                "rag_config_id": rag_config_id,
            }
        created = client.post(
            f"/core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:custom",
            body,
            label=f"node {node_type}",
        )
        nodes[node_type] = require_id(created, "id", f"node {node_type}")

    state.set("node_ids", nodes)
    field("nodes created", len(nodes))
    print("  note: exactly one node may set allow_memory_write=true per flow version.")
    print("  note: rag_config_id is set on EVERY node. ToolResolver resolves its retrieval")
    print("        corpus from the node row (falling back to the agent version), so a node")
    print("        without it retrieves nothing and selects no tool. All nodes must agree:")
    print("        differing values raise 422 flow_snapshot_rag_config_conflict on activate.")
    print("  note: nodes:custom runs validate_node_config, so a node type whose config")
    print("        schema has required fields (MemoryCommitNode: schema_id + rag_config_id,")
    print("        ContextSummarizer: source_node_id) must send them here. Omitting them")
    print("        returns 500, not 400 - the ValidationError escapes uncaught.")


def stage_graph(client: ApiClient, state: DemoState) -> None:
    heading("Graph draft, validate, publish, compile, activate")
    print("  Order matters: nodes:custom upserts the draft and RESETS it to DRAFT, so the")
    print("  full draft is written after the nodes exist; graph:compile then requires a")
    print("  PUBLISHED flow version AND a VALIDATED draft.")
    flow_id = state.get("flow_id")
    flow_version_id = state.get("flow_version_id")
    definition = build_graph_definition(state.get("node_ids"), state.get("rag_config_id"))
    base = f"/core/v1/flows/{flow_id}/versions/{flow_version_id}"

    client.post(
        f"{base}/graph:draft",
        {
            "flow_id": flow_id,
            "flow_version_id": flow_version_id,
            "principal_id": "examples",
            "definition": definition,
        },
        label="upsert graph draft",
    )
    client.post(
        f"{base}/graph:validate",
        {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": "examples"},
        label="validate graph draft",
    )
    client.post(f"{base}:validate", label="validate flow version")
    client.post(
        f"{base}:publish",
        {"change_type": "PUBLISH", "justification": "examples bootstrap"},
        label="publish flow version",
    )
    client.post(
        f"{base}/graph:compile",
        {"flow_id": flow_id, "flow_version_id": flow_version_id, "principal_id": "examples"},
        label="compile graph snapshot",
    )
    client.post(
        f"{base}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate flow version",
    )
    print(
        "  note: graph:compile is one-shot - a second call returns 404 flow_graph_snapshot_exists."
    )


def stage_bindings(client: ApiClient, state: DemoState) -> None:
    heading("Bindings")
    nodes = state.get("node_ids")
    agent_version_id = state.get("agent_version_id")
    for node_type in ("ToolResolver", "ToolInputFiller", "ResponseBuilder"):
        client.post(
            "/core/v1/node-agent-bindings",
            {"node_id": nodes[node_type], "agent_version_id": agent_version_id},
            label=f"bind agent to {node_type}",
        )
    for tool_config_id in state.get("tool_config_ids"):
        client.post(
            "/core/v1/agent-version-tool-bindings",
            {"agent_version_id": agent_version_id, "tool_config_id": tool_config_id},
            label="bind tool to agent version",
        )
    client.post(
        "/core/v1/node-ai-execution-policy-bindings",
        {
            "node_id": nodes["ToolResolver"],
            "ai_execution_policy_version_id": state.get("ai_execution_policy_version_id"),
        },
        label="bind ai execution policy",
    )
    tools = client.get(
        f"/core/v1/agent-versions/{agent_version_id}/tools",
        label="list tools of agent version",
    )
    field("tools bound", len(tools) if isinstance(tools, list) else tools)
    print("  note: the bindings are an allowlist applied AFTER retrieval, not the candidate")
    print("        set. A retrieved tool that is not bound is dropped; an empty binding set")
    print("        disables the filter entirely rather than blocking everything.")


def stage_runtime_policy(client: ApiClient, state: DemoState) -> None:
    heading("Runtime policy")
    policy = client.post(
        "/core/v1/runtime-policies",
        {
            "scope": "TENANT",
            "version": "1",
            "policy_definition": {
                "limits": {
                    "max_nodes": 50,
                    "max_depth": 20,
                    "max_edges_per_node": 3,
                    "max_total_duration_ms": 120000,
                    "max_node_duration_ms": 45000,
                    "max_loop_iterations": 10,
                    "tool_fanout_max_concurrency": 4,
                },
                "execution": {
                    "fail_on_multiple_true_edges": True,
                    "fail_on_missing_graph": True,
                    "allow_parallel_nodes": False,
                    "strict_contract_mode": True,
                },
                "tools": {
                    "max_retries": 2,
                    "circuit_breaker": {"failure_threshold": 5, "window_seconds": 60},
                },
                "llm": {
                    "max_retries": 3,
                    "timeout_ms": 30000,
                    "stream_enabled": True,
                    "stream_eligible_tasks": ["response_render", "clarification"],
                    "history_enabled_tasks": [
                        "tool_selection",
                        "slot_filling",
                        "clarification",
                        "response_render",
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                    "inference_layers": {
                        "cache_enabled": True,
                        "cache_similarity_threshold": 0.95,
                        "cache_ttl_seconds": 3600,
                        "slm_enabled": False,
                        "escalation_on_schema_mismatch": True,
                    },
                },
                "moderation": {
                    "primary": {
                        "provider": "OPENAI",
                        "model_alias": MODERATION_MODEL_ALIAS,
                        "timeout_ms": 3000,
                    },
                    "fallback_enabled": False,
                    "prompt_key": "ContentModeration",
                    "temperature": 0.0,
                    "max_tokens": 18,
                },
                "user_context_enrichment": {
                    "enabled": False,
                    "gating": False,
                    "default_layers_when_published": {
                        "allow_tenant_knowledge": True,
                        "allow_user_memory_structured": True,
                        "allow_user_memory_vector": True,
                    },
                },
                "memory_extraction": {
                    "enabled": True,
                    "rag_config_id": state.get("rag_config_id"),
                    "preference_schema_id": MEMORY_SCHEMA_ID,
                    "profile_schema_id": "user.profile_signal.v1",
                    "llm": {
                        "provider": "OPENAI",
                        "model_alias": "gpt-4o-mini",
                        "prompt": "Extract user preferences from flow output.",
                        "task_type": "MEMORY_EXTRACTION",
                    },
                },
                "memory_retrieval": {
                    "temporal_scoring": {
                        "enabled": False,
                        "half_life_seconds": 604800,
                        "timestamp_source": "OBSERVED_AT",
                        "candidate_multiplier": 3,
                    }
                },
            },
        },
        label="create runtime policy",
    )
    policy_id = require_id(policy, "id", "runtime policy")
    client.post(
        f"/core/v1/runtime-policies/{policy_id}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate runtime policy",
    )
    state.set("runtime_policy_id", policy_id)
    print("  note: runtime policies have no publish step - the lifecycle is create -> :activate.")


def stage_governance(client: ApiClient, state: DemoState) -> None:
    heading("Governance policies")

    access = client.post(
        "/core/v1/access-policies",
        {"name": "examples-access-policy"},
        label="create access policy",
    )
    access_id = require_id(access, "id", "access policy")
    access_version = client.post(
        f"/core/v1/access-policies/{access_id}/versions",
        {
            "status": "DRAFT",
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
            "rules": {"allow": list(ALLOWED_ACTIONS), "deny": None},
        },
        label="create access policy version",
    )
    access_version_id = require_id(access_version, "id", "access policy version")
    client.post(
        f"/core/v1/access-policies/versions/{access_version_id}:publish",
        label="publish access policy version",
    )
    print("  note: access policy rules.allow is a STRICT allowlist of action strings.")
    print("        Once a tenant has a published access policy, any action missing from")
    print("        the list is denied with 403 action_not_allowed.")

    rate = client.post(
        "/core/v1/rate-limit-policies",
        {"name": "examples-rate-limit-policy"},
        label="create rate limit policy",
    )
    rate_id = require_id(rate, "id", "rate limit policy")
    for index, action in enumerate(ALLOWED_ACTIONS):
        rate_version = client.post(
            f"/core/v1/rate-limit-policies/{rate_id}/versions",
            {
                "action": action,
                "principal_type": "human",
                "limit": 1000,
                "window_seconds": 60,
                "status": "DRAFT",
                "version_major": 1,
                "version_minor": index,
                "version_patch": 0,
            },
            label=f"rate limit version {action}",
        )
        rate_version_id = require_id(rate_version, "id", f"rate limit version {action}")
        client.post(
            f"/core/v1/rate-limit-policies/versions/{rate_version_id}:publish",
            label=f"publish rate limit {action}",
        )
    print("  note: rate limiting resolves a PUBLISHED version per action and fails closed.")
    print("        Once a tenant has a rate limit policy, every action it uses needs its")
    print(
        "        own published version or the call is denied 403 rate_limit_policy_not_published."
    )
    print("  note: version semver is unique per policy - reusing 1.0.0 raises an uncaught")
    print("        IntegrityError and surfaces as 500.")

    billing = client.post(
        "/core/v1/billing-policies",
        {"name": "examples-billing-policy"},
        label="create billing policy",
    )
    billing_id = require_id(billing, "id", "billing policy")
    billing_version = client.post(
        f"/core/v1/billing-policies/{billing_id}/versions",
        {
            "status": "DRAFT",
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
            "rules": {},
        },
        label="create billing policy version",
    )
    billing_version_id = require_id(billing_version, "id", "billing policy version")
    client.post(
        f"/core/v1/billing-policies/versions/{billing_version_id}:publish",
        label="publish billing policy version",
    )
    client.post(
        f"/core/v1/billing-policies/versions/{billing_version_id}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate billing policy version",
    )

    memory = client.post(
        "/core/v1/memory-policies",
        {"name": "examples-memory-policy"},
        label="create memory policy",
    )
    memory_id = require_id(memory, "id", "memory policy")
    memory_version = client.post(
        f"/core/v1/memory-policies/{memory_id}/versions",
        {
            "definition": {
                "retention_ttl_seconds": 2592000,
                "consent": {"required": False, "preference_key": "memory.consent"},
                "allowed_sources": ["explicit_user", "tool_output"],
                "allowed_schemas": [
                    {
                        "schema_id": MEMORY_SCHEMA_ID,
                        "write_targets": ["USER_PREFERENCE", "USER_MEMORY_VECTOR"],
                        "preference_update": {
                            "ignore_if_unchanged": True,
                            "overwrite_mode": "SOURCE_PRIORITY",
                        },
                    }
                ],
            },
            "status": "DRAFT",
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
        },
        label="create memory policy version",
    )
    memory_version_id = require_id(memory_version, "id", "memory policy version")
    client.post(
        f"/core/v1/memory-policies/versions/{memory_version_id}:publish",
        label="publish memory policy version",
    )
    client.post(
        f"/core/v1/memory-policies/versions/{memory_version_id}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate memory policy version",
    )
    print("  note: activating a memory policy version clears is_active on every other")
    print("        memory policy version of the tenant, across all policy roots.")

    rag_policy = client.post(
        "/core/v1/rag-policies",
        {"name": "examples-rag-activation-policy"},
        label="create rag policy",
    )
    rag_policy_id = require_id(rag_policy, "id", "rag policy")
    layer = {
        "tenant_knowledge": {"enabled": True, "allowed_tool_config_ids": []},
        "user_memory_vector": {"enabled": True, "allowed_tool_config_ids": []},
    }
    rag_version = client.post(
        f"/core/v1/rag-policies/{rag_policy_id}/versions",
        {
            "definition": {
                "defaults": {
                    "intent_selection": layer,
                    "memory_extraction": layer,
                    "slot_filling": layer,
                    "response_render": layer,
                    "clarification": layer,
                },
                "require_published_rag_config": True,
                "top_k_cap": 5,
                "min_query_chars_by_scope": {"TENANT_KNOWLEDGE": 8, "USER_MEMORY_VECTOR": 8},
                "allow_structured_input": False,
                "ingest_quotas": {"max_documents_per_user": 10},
            },
            "status": "DRAFT",
            "version_major": 1,
            "version_minor": 0,
            "version_patch": 0,
        },
        label="create rag policy version",
    )
    rag_version_id = require_id(rag_version, "id", "rag policy version")
    client.post(
        f"/core/v1/rag-policies/versions/{rag_version_id}:publish",
        label="publish rag policy version",
    )
    client.post(
        f"/core/v1/rag-policies/versions/{rag_version_id}:activate",
        {"change_type": "ACTIVATE", "justification": "examples bootstrap"},
        label="activate rag policy version",
    )

    state.set("access_policy_id", access_id)
    state.set("rate_limit_policy_id", rate_id)
    state.set("billing_policy_id", billing_id)
    state.set("memory_policy_id", memory_id)
    state.set("rag_policy_id", rag_policy_id)


def stage_mcp_server(client: ApiClient, state: DemoState, *, user_prompt_id: str) -> None:
    heading("MCP server")
    mcp = client.post(
        "/core/v1/tenants/mcp-servers",
        {
            "name": "examples-mcp-server",
            "tool_config_ids": state.get("tool_config_ids"),
            "vector_store_ids": [state.get("vector_store_id")],
            "user_prompt_ids": [user_prompt_id],
        },
        label="create mcp server",
    )
    state.set("user_prompt_id", user_prompt_id)
    state.set("mcp_server_id", require_id(mcp, "mcp_server_id", "mcp server"))
    state.set("mcp_endpoint", mcp.get("endpoint"))
    state.set("mcp_api_key", mcp.get("api_key"))
    field("mcp endpoint", mcp.get("endpoint"))
    print("  note: the MCP api_key is returned only here, once - only its hash is stored.")


def require_healthy_api(client: ApiClient, base_url: str) -> None:
    try:
        client.get("/health", label="health check")
    except Exception as exc:
        raise SystemExit(
            f"cannot reach the API at {base_url}: {exc}\n"
            "start it with: PYTHONPATH=src uv run uvicorn src.app:app --port 8000"
        ) from exc
