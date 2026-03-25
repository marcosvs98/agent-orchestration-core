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
from domain.governance.schemas.memory_policy import MemoryWriteTarget
from domain.governance.services.memory_policy_service import MemoryPolicyService
from domain.context.services.memory_writer import MemoryWriteService
from resources.scripts.seeds.demo.ids import RAG_CONFIG_DEMO_ID, TENANT_DEMO_ID
from resources.scripts.seeds.demo.rag_payloads import demo_user_memory_write_item_dict

logger = get_logger(__name__)

CAP = 10


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
    tenant_id = TENANT_DEMO_ID
    user_id = f"rag_quota_{uuid.uuid4().hex[:12]}"
    rag_config_id = RAG_CONFIG_DEMO_ID
    for i in range(CAP):
        item = demo_user_memory_write_item_dict(
            user_id=user_id,
            rag_config_id=rag_config_id,
            utterance=f"quota probe utterance index {i} unique token qx{i:04d}",
            topic="quota_test",
        )
        result = await memory_write_service.write_memory_item(
            tenant_id=tenant_id,
            user_id=user_id,
            item=item,
            event_context=None,
        )
        if MemoryWriteTarget.USER_MEMORY_VECTOR not in result.targets_applied:
            raise SystemExit(
                f"write {i + 1}/{CAP}: expected vector target; got {result.targets_applied!r}"
            )
    count = await rag_runtime_service.count_user_memory_documents_for_rag_config(
        tenant_id=tenant_id,
        user_id=user_id,
        rag_config_id=rag_config_id,
    )
    if count != CAP:
        raise SystemExit(f"expected document count {CAP}; got {count}")
    overflow = demo_user_memory_write_item_dict(
        user_id=user_id,
        rag_config_id=rag_config_id,
        utterance="overflow utterance after cap should not create new vector document",
        topic="quota_test_overflow",
    )
    overflow_result = await memory_write_service.write_memory_item(
        tenant_id=tenant_id,
        user_id=user_id,
        item=overflow,
        event_context=None,
    )
    if MemoryWriteTarget.USER_MEMORY_VECTOR in overflow_result.targets_applied:
        raise SystemExit(
            "expected cap behavior: 11th write must not apply USER_MEMORY_VECTOR "
            f"(got targets_applied={overflow_result.targets_applied!r})"
        )
    count_after = await rag_runtime_service.count_user_memory_documents_for_rag_config(
        tenant_id=tenant_id,
        user_id=user_id,
        rag_config_id=rag_config_id,
    )
    if count_after != CAP:
        raise SystemExit(
            f"after overflow write count must stay {CAP}; got {count_after}"
        )
    logger.info(
        "rag_user_memory_quota_validate_ok",
        tenant_id=str(tenant_id),
        user_id=user_id,
        cap=CAP,
        count_after_overflow=count_after,
    )
    print(
        "\nrag_user_memory_quota_validate_ok",
        f"\ntenant_id={tenant_id}",
        f"\nuser_id={user_id}",
        f"\neffective_cap={CAP}",
        "\noverflow_write_skipped_vector=True",
    )


if __name__ == "__main__":
    asyncio.run(main())
