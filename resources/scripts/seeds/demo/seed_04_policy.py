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
from infra.database.models.ai_policy.execution_policy import AIExecutionPolicy
from infra.database.models.ai_policy.execution_policy_version import (
    AIExecutionPolicyVersion,
)

from seeds.demo.ids import (
    MODEL_DEMO_ID,
    POLICY_DEMO_ID,
    POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
)


async def seed_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(AIExecutionPolicy).where(
                AIExecutionPolicy.ai_execution_policy_id == POLICY_DEMO_ID
            )
        )
        policy = result.scalar_one_or_none()

        if policy is None:
            policy = AIExecutionPolicy(
                ai_execution_policy_id=POLICY_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                description="AI Execution Policy para tenant demo",
            )
            session.add(policy)
            await session.commit()

        result = await session.execute(
            select(AIExecutionPolicyVersion).where(
                AIExecutionPolicyVersion.ai_execution_policy_version_id
                == POLICY_VERSION_V1_ID
            )
        )
        policy_version = result.scalar_one_or_none()

        if policy_version is None:
            policy_version = AIExecutionPolicyVersion(
                ai_execution_policy_version_id=POLICY_VERSION_V1_ID,
                ai_execution_policy_id=POLICY_DEMO_ID,
                model_id=MODEL_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
            )
            session.add(policy_version)
            await session.commit()
