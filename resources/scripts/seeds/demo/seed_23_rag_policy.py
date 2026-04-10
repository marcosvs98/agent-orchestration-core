from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

for _repo in Path(__file__).resolve().parents:
    if (_repo / "pyproject.toml").exists():
        sys.path.insert(0, str(_repo / "src"))
        sys.path.insert(0, str(_repo / "resources" / "scripts"))
        sys.path.insert(0, str(_repo))
        break
else:
    raise RuntimeError("repository root not found")

from sqlalchemy import select, update

from domain.common.schemas.versioning import VersionStatus
from domain.governance.schemas.rag_policy import (
    RagIngestQuotas,
    RagPolicyDefinition,
    RagScopePolicy,
    RagTaskDefaults,
)
from domain.llm.schemas.llm import LLMTaskType
from infra.database import get_db
from infra.database.models.governance.rag_policy import RagPolicy
from infra.database.models.governance.rag_policy_version import RagPolicyVersion
from seeds.demo.ids import (
    PRINCIPAL_SYSTEM,
    RAG_POLICY_DEMO_ID,
    RAG_POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
)


async def seed_rag_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(RagPolicy).where(RagPolicy.rag_policy_id == RAG_POLICY_DEMO_ID)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                RagPolicy(
                    rag_policy_id=RAG_POLICY_DEMO_ID,
                    tenant_id=TENANT_DEMO_ID,
                    name="Uora - RAG Activation Policy",
                )
            )
            await session.commit()

        policy_definition = RagPolicyDefinition.model_validate(
            {
                "defaults": {
                    LLMTaskType.INTENT_SELECTION: RagTaskDefaults(
                        tenant_knowledge=RagScopePolicy(enabled=True),
                        user_memory_vector=RagScopePolicy(
                            enabled=True,
                            allowed_tool_config_ids=[TOOL_CONFIG_DEMO_ID],
                        ),
                    ),
                    LLMTaskType.MEMORY_EXTRACTION: RagTaskDefaults(
                        tenant_knowledge=RagScopePolicy(enabled=True),
                        user_memory_vector=RagScopePolicy(
                            enabled=True,
                            allowed_tool_config_ids=[TOOL_CONFIG_DEMO_ID],
                        ),
                    ),
                    LLMTaskType.SLOT_FILLING: RagTaskDefaults(
                        tenant_knowledge=RagScopePolicy(enabled=True),
                        user_memory_vector=RagScopePolicy(enabled=True),
                    ),
                    LLMTaskType.RESPONSE_RENDER: RagTaskDefaults(
                        tenant_knowledge=RagScopePolicy(enabled=True),
                        user_memory_vector=RagScopePolicy(enabled=True),
                    ),
                    LLMTaskType.CLARIFICATION: RagTaskDefaults(
                        tenant_knowledge=RagScopePolicy(enabled=True),
                        user_memory_vector=RagScopePolicy(enabled=True),
                    ),
                },
                "require_published_rag_config": True,
                "top_k_cap": 5,
                "min_query_chars_by_scope": {
                    "TENANT_KNOWLEDGE": 8,
                    "USER_MEMORY_VECTOR": 8,
                },
                "allow_structured_input": False,
                "ingest_quotas": RagIngestQuotas(max_documents_per_user=10),
            }
        ).model_dump(mode="json")
        result = await session.execute(
            select(RagPolicyVersion).where(
                RagPolicyVersion.rag_policy_version_id == RAG_POLICY_VERSION_V1_ID
            )
        )
        existing_version = result.scalar_one_or_none()
        if existing_version is None:
            session.add(
                RagPolicyVersion(
                    rag_policy_version_id=RAG_POLICY_VERSION_V1_ID,
                    rag_policy_id=RAG_POLICY_DEMO_ID,
                    status=VersionStatus.PUBLISHED.value,
                    version_major=1,
                    version_minor=0,
                    version_patch=0,
                    policy_definition=policy_definition,
                )
            )
            await session.commit()
        else:
            existing_version.policy_definition = policy_definition
            session.add(existing_version)
            await session.commit()

        await session.execute(
            update(RagPolicyVersion)
            .where(
                RagPolicyVersion.tenant_id == TENANT_DEMO_ID,
                RagPolicyVersion.rag_policy_version_id != RAG_POLICY_VERSION_V1_ID,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(RagPolicyVersion)
            .where(
                RagPolicyVersion.rag_policy_version_id == RAG_POLICY_VERSION_V1_ID,
            )
            .values(
                tenant_id=TENANT_DEMO_ID,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="bootstrap rag policy",
            )
        )
        await session.commit()
