from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select, update

from domain.common.schemas.versioning import VersionStatus
from domain.governance.schemas.memory_policy import MemoryPolicyDefinition
from infra.database import get_db
from infra.database.models.governance.memory_policy import MemoryPolicy
from infra.database.models.governance.memory_policy_version import MemoryPolicyVersion
from seeds.demo.ids import (
    MEMORY_POLICY_DEMO_ID,
    MEMORY_POLICY_VERSION_V1_ID,
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
)


async def seed_memory_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(MemoryPolicy).where(
                MemoryPolicy.memory_policy_id == MEMORY_POLICY_DEMO_ID
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            policy = MemoryPolicy(
                memory_policy_id=MEMORY_POLICY_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="Uora - Memory Policy",
            )
            session.add(policy)
            await session.commit()

        result = await session.execute(
            select(MemoryPolicyVersion).where(
                MemoryPolicyVersion.memory_policy_version_id == MEMORY_POLICY_VERSION_V1_ID
            )
        )
        existing_version = result.scalar_one_or_none()
        memory_policy_definition = MemoryPolicyDefinition.model_validate(
            {
                "retention_ttl_seconds": 2_592_000,
                "consent": {
                    "required": False,
                    "preference_key": "memory.consent",
                    "required_for_sources": ["inferred_llm", "tool_output"],
                },
                "allowed_sources": [
                    "explicit_user",
                    "inferred_llm",
                    "tool_output",
                    "admin_seed",
                ],
                "allowed_schemas": [
                    {
                        "schema_id": "user.preference.v1",
                        "max_item_bytes": 4096,
                        "preference_update": {
                            "fixed_key": None,
                            "allowed_keys": [
                                "style.tone",
                                "style.depth",
                                "style.formality",
                            ],
                            "ignore_if_unchanged": True,
                            "overwrite_mode": "SOURCE_PRIORITY",
                        },
                    },
                    {
                        "schema_id": "user.profile_signal.v1",
                        "max_item_bytes": 4096,
                    },
                ],
            }
        ).model_dump(mode="json")
        if existing_version is None:
            policy_version = MemoryPolicyVersion(
                memory_policy_version_id=MEMORY_POLICY_VERSION_V1_ID,
                memory_policy_id=MEMORY_POLICY_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                retention_ttl_seconds=memory_policy_definition["retention_ttl_seconds"],
                consent_definition=memory_policy_definition["consent"],
                allowed_sources=memory_policy_definition["allowed_sources"],
                allowed_schemas=memory_policy_definition["allowed_schemas"],
            )
            session.add(policy_version)
            await session.commit()

        await session.execute(
            update(MemoryPolicyVersion)
            .where(
                MemoryPolicyVersion.tenant_id == TENANT_DEMO_ID,
                MemoryPolicyVersion.memory_policy_version_id != MEMORY_POLICY_VERSION_V1_ID,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(MemoryPolicyVersion)
            .where(
                MemoryPolicyVersion.memory_policy_version_id == MEMORY_POLICY_VERSION_V1_ID,
            )
            .values(
                tenant_id=TENANT_DEMO_ID,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
                activated_by_principal_id=PRINCIPAL_SYSTEM,
                justification="bootstrap memory policy",
            )
        )
        await session.commit()
