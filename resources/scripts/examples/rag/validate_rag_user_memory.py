from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

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

from adapters.observability.logging import get_logger
from containers import ApplicationContainer
from domain.context.schemas.context_layers import UserMemoryQuery
from domain.context.services.memory_writer import MemoryWriteService
from domain.context.services.retrievers import UserMemoryReader
from domain.governance.schemas.memory_policy import MemoryWriteTarget
from domain.governance.services.memory_policy_service import MemoryPolicyService
from resources.scripts.seeds.demo.ids import RAG_CONFIG_DEMO_ID, TENANT_DEMO_ID
from resources.scripts.seeds.demo.rag_payloads import demo_user_memory_write_item_dict

logger = get_logger(__name__)


async def main() -> None:
    app = ApplicationContainer()
    execution_repository = app.execution.execution_repository()
    rag_runtime_service = app.rag.rag_runtime_service()
    tracer = app.adapters.tracer()
    memory_policy_service = MemoryPolicyService(repository=execution_repository)
    memory_write_service = MemoryWriteService(
        policy_service=memory_policy_service,
        rag_runtime_service=rag_runtime_service,
        repository=execution_repository,
        tracer=tracer,
        embedding_job_queue=None,
    )
    user_memory_reader = UserMemoryReader(
        repository=execution_repository,
        rag_runtime_service=rag_runtime_service,
        memory_policy_service=memory_policy_service,
        rag_activation_service=None,
    )
    tenant_id = TENANT_DEMO_ID
    user_id = f"rag_validate_{uuid.uuid4().hex[:12]}"
    utterance = (
        "I have a preference for dividend-paying equities and income-oriented portfolios."
    )
    write_item = demo_user_memory_write_item_dict(
        user_id=user_id,
        rag_config_id=RAG_CONFIG_DEMO_ID,
        utterance=utterance,
        topic="investment_preferences",
    )
    write_result = await memory_write_service.write_memory_item(
        tenant_id=tenant_id,
        user_id=user_id,
        item=write_item,
        event_context=None,
    )
    if MemoryWriteTarget.USER_MEMORY_VECTOR not in write_result.targets_applied:
        raise SystemExit(
            f"expected vector write; got {write_result.targets_applied!r}"
        )
    query_text = (
        "Qual a preferência deste usuário em relação a dividendos e estilo de renda da carteira?"
    )
    memory_ctx = await user_memory_reader.get_context(
        query=UserMemoryQuery(
            tenant_id=tenant_id,
            user_id=user_id,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            user_input=query_text,
        ),
        task_type=None,
    )
    rag = memory_ctx.rag_context
    if rag is None or not rag.context_items:
        raise SystemExit("expected at least one RAG hit for user memory query")
    top = max(rag.context_items, key=lambda it: it.score)
    print(
        "rag_user_memory_validate_ok",
        f"\ntenant_id={tenant_id}",
        f"\nuser_id={user_id}",
        f"\ndocument_id={top.document_id}",
        f"\nscore={top.score}",
        f"\ncontent_prefix={top.content[:200]}",
    )


if __name__ == "__main__":
    asyncio.run(main())
