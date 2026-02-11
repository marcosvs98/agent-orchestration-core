from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from infra.database import get_db
from infra.database.models.governance.active_rag_policy_version import (
    ActiveRagPolicyVersion,
)
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
                    name="Demo RAG Activation Policy",
                )
            )
            await session.commit()

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
                    policy_definition={
                        "defaults": {
                            "INTENT_SELECTION": {
                                "tenant_knowledge": {"enabled": True},
                                "user_memory_vector": {
                                    "enabled": True,
                                    "allowed_tool_config_ids": [
                                        str(TOOL_CONFIG_DEMO_ID)
                                    ],
                                },
                            },
                            "SLOT_FILLING": {
                                "tenant_knowledge": {"enabled": True},
                                "user_memory_vector": {"enabled": True},
                            },
                            "RESPONSE_RENDER": {
                                "tenant_knowledge": {"enabled": True},
                                "user_memory_vector": {"enabled": True},
                            },
                            "CLARIFICATION": {
                                "tenant_knowledge": {"enabled": False},
                                "user_memory_vector": {"enabled": False},
                            },
                        },
                        "require_published_rag_config": True,
                        "top_k_cap": 5,
                    },
                )
            )
            await session.commit()

        result = await session.execute(
            select(ActiveRagPolicyVersion).where(
                ActiveRagPolicyVersion.tenant_id == TENANT_DEMO_ID
            )
        )
        active_version = result.scalar_one_or_none()
        if active_version is None:
            active_version = ActiveRagPolicyVersion(
                tenant_id=TENANT_DEMO_ID,
                rag_policy_version_id=RAG_POLICY_VERSION_V1_ID,
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="bootstrap rag policy",
            )
        else:
            active_version.rag_policy_version_id = RAG_POLICY_VERSION_V1_ID
            active_version.activated_by_principal_id = PRINCIPAL_SYSTEM
            active_version.justification = "bootstrap rag policy"
        session.add(active_version)
        await session.commit()
