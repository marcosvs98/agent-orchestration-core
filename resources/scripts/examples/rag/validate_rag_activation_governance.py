from __future__ import annotations

import asyncio
import sys
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
from domain.context.services.rag_activation_service import RagActivationService
from domain.governance.schemas.rag_policy import RagActivationScope
from domain.llm.schemas.llm import LLMTaskType
from resources.scripts.seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
)


def _expect(
    *,
    got: bool,
    expected: bool,
    label: str,
) -> None:
    if got != expected:
        raise SystemExit(f"matrix row {label}: expected enabled={expected}; got {got}")


async def main() -> None:
    app = ApplicationContainer()
    tenant_id = TENANT_DEMO_ID
    rag_config_id = RAG_CONFIG_DEMO_ID
    tool_config_id: UUID = TOOL_CONFIG_DEMO_ID
    execution_repository = app.execution.execution_repository()
    rag_repository = app.rag.rag_repository()
    rag_policy_service = app.rag.rag_policy_service()
    tools_repository = app.tools.tools_repository()
    tracer = app.adapters.tracer()
    svc = RagActivationService(
        repository=execution_repository,
        rag_repository=rag_repository,
        tools_repository=tools_repository,
        rag_policy_service=rag_policy_service,
        tracer=tracer,
    )
    long_text = "tenant knowledge retrieval probe with enough characters"
    d1 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.INTENT_SELECTION,
        scope=RagActivationScope.TENANT_KNOWLEDGE,
        task_flags=AITaskContextFlags(
            allow_rag_tenant=True,
            rag_config_id=rag_config_id,
        ),
        rag_config_id=rag_config_id,
        user_input=long_text,
    )
    _expect(got=d1.enabled, expected=True, label="tenant_knowledge_allowed")
    d2 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.INTENT_SELECTION,
        scope=RagActivationScope.TENANT_KNOWLEDGE,
        task_flags=AITaskContextFlags(
            allow_rag_tenant=False,
            rag_config_id=rag_config_id,
        ),
        rag_config_id=rag_config_id,
        user_input=long_text,
    )
    _expect(got=d2.enabled, expected=False, label="tenant_knowledge_structural_deny")
    d3 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.INTENT_SELECTION,
        scope=RagActivationScope.TENANT_KNOWLEDGE,
        task_flags=None,
        rag_config_id=rag_config_id,
        user_input=long_text,
    )
    _expect(got=d3.enabled, expected=False, label="tenant_knowledge_flags_none")
    d4 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.INTENT_SELECTION,
        scope=RagActivationScope.TENANT_KNOWLEDGE,
        task_flags=AITaskContextFlags(
            allow_rag_tenant=True,
            rag_config_id=rag_config_id,
        ),
        rag_config_id=rag_config_id,
        user_input="short",
    )
    _expect(got=d4.enabled, expected=False, label="tenant_knowledge_input_too_short")
    user_id = "rag_activation_matrix_user"
    um_text = "user memory vector probe with sufficient length for heuristics"
    d5 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.MEMORY_EXTRACTION,
        scope=RagActivationScope.USER_MEMORY_VECTOR,
        task_flags=AITaskContextFlags(
            allow_user_memory_vector=True,
            rag_config_id=rag_config_id,
        ),
        rag_config_id=rag_config_id,
        user_id=user_id,
        user_input=um_text,
        tool_config_id=tool_config_id,
    )
    _expect(got=d5.enabled, expected=True, label="user_memory_vector_allowed")
    d6 = await svc.decide(
        tenant_id=tenant_id,
        task_type=LLMTaskType.MEMORY_EXTRACTION,
        scope=RagActivationScope.USER_MEMORY_VECTOR,
        task_flags=AITaskContextFlags(
            allow_user_memory_vector=True,
            rag_config_id=rag_config_id,
        ),
        rag_config_id=rag_config_id,
        user_id=None,
        user_input=um_text,
        tool_config_id=tool_config_id,
    )
    _expect(got=d6.enabled, expected=False, label="user_memory_vector_missing_user_id")
    print(
        "\nrag_activation_governance_ok",
        "\nrows=6",
        f"\ntenant_knowledge_reason_ok={d1.reason.value}",
        f"\nuser_memory_reason_ok={d5.reason.value}",
    )


if __name__ == "__main__":
    asyncio.run(main())
