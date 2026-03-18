from __future__ import annotations

import pytest
import sqlalchemy as sa

from infra.database.models.flow.flow_version import FlowVersion
from infra.database.models.governance.access_policy_version import AccessPolicyVersion
from infra.database.models.governance.execution_limit_policy_version import ExecutionLimitPolicyVersion
from infra.database.models.governance.rate_limit_policy_version import RateLimitPolicyVersion
from resources.scripts.validation_seed import (
    ACCESS_POLICY_VERSION_ID,
    DRAFT_FLOW_ID,
    EXEC_LIMIT_VERSION_ID,
    RATE_LIMIT_VERSION_ID,
)
from .evidence import json_block, text_block, write_markdown

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_fail_closed_and_limits_present(db_session) -> None:
    result = await db_session.execute(
        sa.select(FlowVersion).where(
            FlowVersion.flow_id == DRAFT_FLOW_ID,
            FlowVersion.is_active.is_(True),
        )
    )
    assert result.scalar_one_or_none() is None

    exec_limit_result = await db_session.execute(
        sa.select(ExecutionLimitPolicyVersion).where(
            ExecutionLimitPolicyVersion.execution_limit_policy_version_id == EXEC_LIMIT_VERSION_ID
        )
    )
    exec_limit = exec_limit_result.scalar_one_or_none()

    rate_limit_result = await db_session.execute(
        sa.select(RateLimitPolicyVersion).where(
            RateLimitPolicyVersion.rate_limit_policy_version_id == RATE_LIMIT_VERSION_ID
        )
    )
    rate_limit = rate_limit_result.scalar_one_or_none()

    access_policy_result = await db_session.execute(
        sa.select(AccessPolicyVersion).where(
            AccessPolicyVersion.access_policy_version_id == ACCESS_POLICY_VERSION_ID
        )
    )
    access_policy = access_policy_result.scalar_one_or_none()

    assert exec_limit is not None and exec_limit.status == "PUBLISHED"
    assert rate_limit is not None and rate_limit.status == "PUBLISHED"
    assert access_policy is not None and access_policy.status == "PUBLISHED"

    write_markdown(
        "hard-limits-checklist.md",
        [
            text_block(
                "Fail-closed guarantees",
                "Flows without active pointers stay blocked; policies for execution limits, rate limits, and access are present and published.",
            ),
            json_block(
                "Policies",
                {
                    "execution_limit_policy_version_id": str(EXEC_LIMIT_VERSION_ID),
                    "rate_limit_policy_version_id": str(RATE_LIMIT_VERSION_ID),
                    "access_policy_version_id": str(ACCESS_POLICY_VERSION_ID),
                },
            ),
        ],
    )
