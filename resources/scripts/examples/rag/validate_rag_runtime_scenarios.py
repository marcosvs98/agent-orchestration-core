from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from uuid import UUID

for project_root in Path(__file__).resolve().parents:
    if (project_root / "pyproject.toml").exists():
        src_path = project_root / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        break
else:
    raise SystemExit("repository root not found")

from containers import ApplicationContainer
from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.schemas.context_layers import TenantKnowledgeQuery, UserMemoryQuery
from domain.context.services.memory_writer import MemoryWriteService
from domain.context.services.rag_activation_service import RagActivationService
from domain.context.services.retrievers import TenantKnowledgeRetriever, UserMemoryReader
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.graph_runtime.nodes.intent_examples_retriever import (
    IntentExamplesRetriever,
    IntentSemanticMatch,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.governance.schemas.memory_policy import MemoryWriteTarget
from domain.governance.schemas.rag_policy import RagActivationScope
from domain.governance.services.memory_policy_service import MemoryPolicyService
from domain.llm.schemas.llm import LLMTaskType
from domain.rag.schemas.rag import RagContextItem
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.services.tool_catalog_retriever import ToolCatalogRetriever
from resources.scripts.seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)
from resources.scripts.seeds.demo.rag_payloads import (
    demo_intent_examples_probe_document,
    demo_tenant_knowledge_probe_document,
    demo_tool_catalog_probe_document,
    demo_user_memory_write_item_dict,
)


async def scenario_tenant_knowledge(
    *,
    tenant_id: UUID,
    rag_config_id: UUID,
    rag_runtime_service: RagRuntimeService,
    rag_activation: RagActivationService,
) -> RagContextItem:
    tenant_query = (
        "O Assistente de Bolso é uma IA de controle financeiro pessoal pelo WhatsApp; "
        "organiza receitas, despesas, saldos e metas financeiras."
    )
    run_ref = uuid.uuid4().hex
    await rag_runtime_service.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=demo_tenant_knowledge_probe_document(run_ref=run_ref),
    )
    flags = AITaskContextFlags(
        allow_rag_tenant=True,
        rag_config_id=rag_config_id,
    )
    decision = await rag_activation.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.INTENT_SELECTION,
        scope=RagActivationScope.TENANT_KNOWLEDGE,
        task_flags=flags,
        rag_config_id=rag_config_id,
        user_input=tenant_query,
    )
    if not decision.enabled:
        raise SystemExit(
            f"scenario_policy_tenant_knowledge: denied reason={decision.reason!s}"
        )
    tenant_retriever = TenantKnowledgeRetriever(rag_runtime_service)
    tenant_ctx = await tenant_retriever.retrieve(
        query=TenantKnowledgeQuery(
            tenant_id=tenant_id,
            rag_config_id=rag_config_id,
            user_input=tenant_query,
        ),
        top_k_override=decision.effective_top_k,
    )
    tr = tenant_ctx.rag_context
    if tr is None or not tr.context_items:
        raise SystemExit("scenario_tenant_knowledge_retrieval: no context items")
    return max(tr.context_items, key=lambda it: it.score)


async def scenario_user_memory_vector(
    *,
    tenant_id: UUID,
    rag_config_id: UUID,
    execution_repository: ExecutionRepository,
    rag_runtime_service: RagRuntimeService,
    rag_activation: RagActivationService,
    tracer: RuntimeTracerPort,
) -> tuple[str, RagContextItem]:
    memory_policy_service = MemoryPolicyService(repository=execution_repository)
    memory_write_service = MemoryWriteService(
        policy_service=memory_policy_service,
        rag_runtime_service=rag_runtime_service,
        repository=execution_repository,
        tracer=tracer,
        embedding_job_queue=None,
    )
    user_id = f"rag_scenarios_{uuid.uuid4().hex[:12]}"
    utterance = (
        "Prefiro poupança e aplicações de baixo risco e evito ativos muito voláteis."
    )
    write_item = demo_user_memory_write_item_dict(
        user_id=user_id,
        rag_config_id=rag_config_id,
        utterance=utterance,
        topic="risk_preferences",
    )
    write_result = await memory_write_service.write_memory_item(
        tenant_id=tenant_id,
        user_id=user_id,
        item=write_item,
        event_context=None,
    )
    if MemoryWriteTarget.USER_MEMORY_VECTOR not in write_result.targets_applied:
        raise SystemExit(
            f"scenario_user_memory_write: missing vector target {write_result.targets_applied!r}"
        )
    flags_um = AITaskContextFlags(
        allow_user_memory_vector=True,
        rag_config_id=rag_config_id,
    )
    decision_um = await rag_activation.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.MEMORY_EXTRACTION,
        scope=RagActivationScope.USER_MEMORY_VECTOR,
        task_flags=flags_um,
        rag_config_id=rag_config_id,
        user_id=user_id,
        user_input=utterance,
        tool_config_id=TOOL_CONFIG_DEMO_ID,
    )
    if not decision_um.enabled:
        raise SystemExit(
            f"scenario_policy_user_memory: denied reason={decision_um.reason!s}"
        )
    user_memory_reader = UserMemoryReader(
        repository=execution_repository,
        rag_runtime_service=rag_runtime_service,
        memory_policy_service=memory_policy_service,
        rag_activation_service=rag_activation,
    )
    memory_ctx = await user_memory_reader.get_context(
        query=UserMemoryQuery(
            tenant_id=tenant_id,
            user_id=user_id,
            rag_config_id=rag_config_id,
            user_input=utterance,
        ),
        task_type=LLMTaskType.MEMORY_EXTRACTION,
        task_flags=flags_um,
        tool_config_id=TOOL_CONFIG_DEMO_ID,
    )
    ur = memory_ctx.rag_context
    if ur is None or not ur.context_items:
        raise SystemExit("scenario_user_memory_retrieval: no context items")
    top_um = max(ur.context_items, key=lambda it: it.score)
    return user_id, top_um


async def scenario_intent_examples(
    *,
    tenant_id: UUID,
    rag_config_id: UUID,
    rag_runtime_service: RagRuntimeService,
    tracer: RuntimeTracerPort,
) -> IntentSemanticMatch:
    intent_user_input = "Quanto eu gastei neste mês"
    run_ref = uuid.uuid4().hex
    await rag_runtime_service.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=demo_intent_examples_probe_document(
            user_input=intent_user_input,
            run_ref=run_ref,
        ),
    )
    intent_retriever = IntentExamplesRetriever(rag_runtime_service, tracer)
    intent_match = await intent_retriever.retrieve_best_match(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        user_input=intent_user_input,
        top_k=3,
    )
    if intent_match is None:
        raise SystemExit("scenario_intent_examples: no semantic match")
    return intent_match


async def scenario_tool_catalog(
    *,
    tenant_id: UUID,
    rag_config_id: UUID,
    rag_runtime_service: RagRuntimeService,
    tracer: RuntimeTracerPort,
    tools_repository: ToolsRepository,
) -> tuple[str, float, int]:
    tool_user_input = "gastei 80 reais no mercado com cartão"
    run_ref = uuid.uuid4().hex
    await rag_runtime_service.ingest_document(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        document=demo_tool_catalog_probe_document(
            user_input=tool_user_input,
            tool_id=TOOL_DEMO_ID,
            tool_config_id=TOOL_CONFIG_DEMO_ID,
            run_ref=run_ref,
        ),
    )
    tool_retriever = ToolCatalogRetriever(
        rag_runtime_service, tracer, tools_repository
    )
    tool_candidates, tool_evidence = await tool_retriever.retrieve_candidates(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        user_input=tool_user_input,
        top_k=3,
    )
    if not tool_candidates:
        raise SystemExit("scenario_tool_catalog: no ranked tools")
    top = tool_candidates[0]
    return top.name, float(top.retrieval_score or 0.0), len(tool_evidence)


async def main() -> None:
    app = ApplicationContainer()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    execution_repository = app.execution.execution_repository()
    rag_repository = app.rag.rag_repository()
    rag_runtime_service = app.rag.rag_runtime_service()
    rag_policy_service = app.rag.rag_policy_service()
    tools_repository = app.tools.tools_repository()
    tracer = app.adapters.tracer()
    rag_activation = RagActivationService(
        repository=execution_repository,
        rag_repository=rag_repository,
        tools_repository=tools_repository,
        rag_policy_service=rag_policy_service,
        tracer=tracer,
    )
    '''
    top_tenant = await scenario_tenant_knowledge(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        rag_runtime_service=rag_runtime_service,
        rag_activation=rag_activation,
    )
    print(
        "\nscenario_tenant_knowledge: ",
        f"\nscenario_policy_tenant_knowledge: enabled reason_ok \ntop_score={top_tenant.score:.4f}",
        f"\nscenario_tenant_knowledge: document_id={top_tenant.document_id} prefix={top_tenant.content[:120]!r}"
    )


    user_id, top_um = await scenario_user_memory_vector(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        execution_repository=execution_repository,
        rag_runtime_service=rag_runtime_service,
        rag_activation=rag_activation,
        tracer=tracer,
    )
    print(
        f"\nscenario_user_memory: "
        f"\nuser_id={user_id} "
        f"\ndocument_id={top_um.document_id} "
        f"\nprefix={top_um.content[:120]!r}",
    )


    intent_match = await scenario_intent_examples(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
    )
    print(f"\nscenario_intent_examples: "
          f"\nintent={intent_match.intent_type.value} "
          f"\nscore={intent_match.score:.4f}",)
    '''
    top_name, top_score, evidence_n = await scenario_tool_catalog(
        tenant_id=tenant_id,
        rag_config_id=rag_config_id,
        rag_runtime_service=rag_runtime_service,
        tracer=tracer,
        tools_repository=tools_repository,
    )
    print(
        f"\nscenario_tool_catalog: "
        f"\ntool={top_name} "
        f"\nscore={top_score:.4f} evidence_ops={evidence_n}",
    )


if __name__ == "__main__":
    asyncio.run(main())
