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
from infra.database.models.governance.billing_policy import BillingPolicy
from infra.database.models.governance.billing_policy_version import BillingPolicyVersion

from seeds.demo.ids import (
    BILLING_POLICY_DEMO_ID,
    BILLING_POLICY_VERSION_V1_ID,
    TENANT_DEMO_ID,
)


async def seed_billing_policy() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(BillingPolicy).where(
                BillingPolicy.billing_policy_id == BILLING_POLICY_DEMO_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            billing_policy = BillingPolicy(
                billing_policy_id=BILLING_POLICY_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="Uora - Billing Policy",
            )
            session.add(billing_policy)
            await session.commit()

        result = await session.execute(
            select(BillingPolicyVersion).where(
                BillingPolicyVersion.billing_policy_version_id
                == BILLING_POLICY_VERSION_V1_ID
            )
        )
        existing_version = result.scalar_one_or_none()

        if existing_version is None:
            billing_policy_version = BillingPolicyVersion(
                billing_policy_version_id=BILLING_POLICY_VERSION_V1_ID,
                billing_policy_id=BILLING_POLICY_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
            )
            session.add(billing_policy_version)
            await session.commit()
