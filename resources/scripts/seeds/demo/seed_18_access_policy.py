from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.governance.schemas.scopes import Scope
from infra.database import get_db
from infra.database.models.governance.access_policy import AccessPolicy
from infra.database.models.governance.access_policy_version import AccessPolicyVersion

from seeds.demo.ids import (
    ACCESS_POLICY_DEMO_ID,
    ACCESS_POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
)


async def seed_access_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(AccessPolicy).where(
                AccessPolicy.access_policy_id == ACCESS_POLICY_DEMO_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            access_policy = AccessPolicy(
                access_policy_id=ACCESS_POLICY_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="Demo Access Policy",
            )
            session.add(access_policy)
            await session.commit()

        result = await session.execute(
            select(AccessPolicyVersion).where(
                AccessPolicyVersion.access_policy_version_id
                == ACCESS_POLICY_VERSION_V1_ID
            )
        )
        existing_version = result.scalar_one_or_none()

        if existing_version is None:
            all_scopes = [scope.value for scope in Scope]
            access_policy_version = AccessPolicyVersion(
                access_policy_version_id=ACCESS_POLICY_VERSION_V1_ID,
                access_policy_id=ACCESS_POLICY_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                rules={"allow": all_scopes},
            )
            session.add(access_policy_version)
            await session.commit()
        else:
            updated = False
            if existing_version.status != VersionStatus.PUBLISHED.value:
                existing_version.status = VersionStatus.PUBLISHED.value
                updated = True
            if not existing_version.rules or not existing_version.rules.get("allow"):
                all_scopes = [scope.value for scope in Scope]
                existing_version.rules = {"allow": all_scopes}
                updated = True
            if updated:
                session.add(existing_version)
                await session.commit()
