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
from infra.database.models.governance.rate_limit_policy import RateLimitPolicy
from infra.database.models.governance.rate_limit_policy_version import (
    RateLimitPolicyVersion,
)

from domain.governance.schemas.scopes import Scope

from seeds.demo.ids import (
    RATE_LIMIT_POLICY_DEMO_ID,
    RATE_LIMIT_POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
)


async def seed_rate_limit_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(RateLimitPolicy).where(
                RateLimitPolicy.rate_limit_policy_id == RATE_LIMIT_POLICY_DEMO_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            rate_limit_policy = RateLimitPolicy(
                rate_limit_policy_id=RATE_LIMIT_POLICY_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="Demo Rate Limit Policy",
            )
            session.add(rate_limit_policy)
            await session.commit()

        result = await session.execute(
            select(RateLimitPolicyVersion).where(
                RateLimitPolicyVersion.rate_limit_policy_version_id
                == RATE_LIMIT_POLICY_VERSION_V1_ID
            )
        )
        existing_version = result.scalar_one_or_none()

        if existing_version is None:
            rate_limit_policy_version = RateLimitPolicyVersion(
                rate_limit_policy_version_id=RATE_LIMIT_POLICY_VERSION_V1_ID,
                rate_limit_policy_id=RATE_LIMIT_POLICY_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                action=str(Scope.ExecutionFlowRunCreate),
                principal_type="human",
                limit=100,
                window_seconds=60,
            )
            session.add(rate_limit_policy_version)
            await session.commit()
        else:
            updated = False
            if existing_version.action != str(Scope.ExecutionFlowRunCreate):
                existing_version.action = str(Scope.ExecutionFlowRunCreate)
                updated = True
            if existing_version.principal_type != "human":
                existing_version.principal_type = "human"
                updated = True
            if existing_version.status != VersionStatus.PUBLISHED.value:
                existing_version.status = VersionStatus.PUBLISHED.value
                updated = True
            if updated:
                session.add(existing_version)
                await session.commit()
