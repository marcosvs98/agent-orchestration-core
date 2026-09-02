from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select, update

from domain.common.schemas.versioning import VersionStatus
from domain.governance.schemas.scopes import Scope
from infra.database import get_db
from infra.database.models.governance.access_policy import AccessPolicy
from infra.database.models.governance.billing_policy import BillingPolicy
from infra.database.models.governance.billing_policy_version import BillingPolicyVersion
from infra.database.models.governance.access_policy_version import AccessPolicyVersion
from infra.database.models.governance.rate_limit_policy import RateLimitPolicy
from infra.database.models.governance.rate_limit_policy_version import RateLimitPolicyVersion
from infra.database.models.governance.tenant_mcp_credential import TenantMcpCredential

TENANT_DEMO_ID = UUID("00000000-0000-0000-0000-000000000100")
POLICY_NAMESPACE = UUID("00000000-0000-0000-0000-0000000019ff")

STRESS_ACTIONS = (
    str(Scope.ExecutionFlowRunCreate),
    str(Scope.ExecutionFlowRunGet),
    str(Scope.ExecutionFlowRunResume),
    str(Scope.ExecutionGraphStateGet),
    str(Scope.ExecutionNodeRunsList),
    str(Scope.ExecutionEventsList),
    str(Scope.ExecutionAgentRunCreate),
    str(Scope.ExecutionAgentRunGet),
    str(Scope.ExecutionAgentRunCancel),
    str(Scope.ExecutionAgentRunsList),
    str(Scope.ConversationTurnCreate),
    str(Scope.AgentsCardGet),
    str(Scope.AgentsA2ASend),
)

PRINCIPAL_TYPES = ("machine", "human")


async def ensure_policy(tenant_id: UUID) -> UUID:
    async with get_db() as session:
        result = await session.execute(
            select(RateLimitPolicy).where(RateLimitPolicy.tenant_id == tenant_id)
        )
        policy = result.scalars().first()
        if policy is not None:
            return policy.rate_limit_policy_id

        policy_id = uuid5(POLICY_NAMESPACE, f"{tenant_id}:stress")
        session.add(
            RateLimitPolicy(
                rate_limit_policy_id=policy_id,
                tenant_id=tenant_id,
                name="Stress - Rate Limit Policy",
            )
        )
        await session.commit()
        return policy_id


async def publish_versions(policy_id: UUID, limit: int, window_seconds: int) -> tuple[int, int]:
    created = 0
    updated = 0
    async with get_db() as session:
        result = await session.execute(
            select(RateLimitPolicyVersion).where(
                RateLimitPolicyVersion.rate_limit_policy_id == policy_id
            )
        )
        rows = list(result.scalars().all())
        by_target = {(row.action, row.principal_type): row for row in rows}
        next_minor = max((row.version_minor for row in rows), default=-1) + 1

        pending: list[RateLimitPolicyVersion] = []
        for action in STRESS_ACTIONS:
            for principal_type in PRINCIPAL_TYPES:
                existing = by_target.get((action, principal_type))
                if existing is not None:
                    if (
                        existing.limit != limit
                        or existing.window_seconds != window_seconds
                        or existing.status != VersionStatus.PUBLISHED.value
                    ):
                        existing.limit = limit
                        existing.window_seconds = window_seconds
                        existing.status = VersionStatus.PUBLISHED.value
                        updated += 1
                    continue
                pending.append(
                    RateLimitPolicyVersion(
                        rate_limit_policy_version_id=uuid5(
                            POLICY_NAMESPACE, f"{policy_id}:{action}:{principal_type}"
                        ),
                        rate_limit_policy_id=policy_id,
                        status=VersionStatus.PUBLISHED.value,
                        version_major=1,
                        version_minor=next_minor,
                        version_patch=0,
                        action=action,
                        principal_type=principal_type,
                        limit=limit,
                        window_seconds=window_seconds,
                    )
                )
                next_minor += 1
                created += 1

        session.add_all(pending)
        await session.commit()
    return created, updated


async def publish_access_policy_version(tenant_id: UUID) -> tuple[UUID | None, list[str]]:
    async with get_db() as session:
        result = await session.execute(
            select(AccessPolicy).where(AccessPolicy.tenant_id == tenant_id)
        )
        policy = result.scalars().first()
        if policy is None:
            return None, []

        result = await session.execute(
            select(AccessPolicyVersion)
            .where(AccessPolicyVersion.access_policy_id == policy.access_policy_id)
            .order_by(
                AccessPolicyVersion.version_major.desc(),
                AccessPolicyVersion.version_minor.desc(),
                AccessPolicyVersion.version_patch.desc(),
            )
        )
        versions = list(result.scalars().all())
        latest = versions[0] if versions else None
        allowed = list((latest.rules or {}).get("allow", [])) if latest is not None else []

        missing = [action for action in STRESS_ACTIONS if action not in allowed]
        if not missing:
            return None, []

        version_id = uuid5(POLICY_NAMESPACE, f"{policy.access_policy_id}:stress")
        session.add(
            AccessPolicyVersion(
                access_policy_version_id=version_id,
                access_policy_id=policy.access_policy_id,
                status=VersionStatus.PUBLISHED.value,
                version_major=(latest.version_major if latest else 1),
                version_minor=(latest.version_minor + 1) if latest else 0,
                version_patch=0,
                rules={"allow": sorted(set(allowed) | set(STRESS_ACTIONS))},
            )
        )
        await session.commit()
        return version_id, missing


async def activate_billing_policy(tenant_id: UUID) -> UUID | None:
    async with get_db() as session:
        result = await session.execute(
            select(BillingPolicyVersion)
            .join(
                BillingPolicy,
                BillingPolicy.billing_policy_id == BillingPolicyVersion.billing_policy_id,
            )
            .where(BillingPolicy.tenant_id == tenant_id)
            .where(BillingPolicyVersion.status == VersionStatus.PUBLISHED.value)
            .order_by(
                BillingPolicyVersion.version_major.desc(),
                BillingPolicyVersion.version_minor.desc(),
                BillingPolicyVersion.version_patch.desc(),
            )
        )
        versions = list(result.scalars().all())
        if not versions:
            return None

        target = versions[0]
        if target.tenant_id == tenant_id and target.is_active:
            return None

        for version in versions:
            version.is_active = False
        target.tenant_id = tenant_id
        target.is_active = True
        target.activated_at = datetime.now(UTC)
        target.justification = "enabled for stress testing"
        await session.commit()
        return target.billing_policy_version_id


async def set_mcp_revocation(tenant_id: UUID, *, revoked: bool) -> int:
    async with get_db() as session:
        stmt = (
            update(TenantMcpCredential)
            .where(TenantMcpCredential.tenant_id == tenant_id)
            .values(revoked_at=datetime.now(UTC) if revoked else None)
        )
        result = await session.execute(stmt)
        await session.commit()
        return int(result.rowcount or 0)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a tenant for stress testing: publish rate-limit policies for every "
        "action the driver exercises, and optionally park the tenant MCP credential."
    )
    parser.add_argument("--tenant-id", type=UUID, default=TENANT_DEMO_ID)
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--window-seconds", type=int, default=60)
    parser.add_argument(
        "--revoke-mcp",
        action="store_true",
        help="Revoke tenant MCP credentials so conversation turns do not depend on an external "
        "MCP server being reachable.",
    )
    parser.add_argument(
        "--restore-mcp",
        action="store_true",
        help="Undo --revoke-mcp.",
    )
    args = parser.parse_args()

    if args.revoke_mcp and args.restore_mcp:
        print("choose either --revoke-mcp or --restore-mcp, not both", file=sys.stderr)
        return 2

    policy_id = await ensure_policy(args.tenant_id)
    created, updated = await publish_versions(policy_id, args.limit, args.window_seconds)
    print(f"rate-limit policy      : {policy_id}")
    print(f"versions created       : {created}")
    print(f"versions updated       : {updated}")
    print(f"limit                  : {args.limit} per {args.window_seconds}s per principal")

    billing_version_id = await activate_billing_policy(args.tenant_id)
    if billing_version_id is None:
        print("billing policy         : already active (or none published)")
    else:
        print(f"billing policy version : {billing_version_id} (activated)")

    version_id, added = await publish_access_policy_version(args.tenant_id)
    if version_id is None:
        print("access policy          : already allows every stress action")
    else:
        print(f"access policy version  : {version_id} (published)")
        print(f"actions added          : {', '.join(added)}")

    if args.revoke_mcp:
        print(f"mcp credentials revoked: {await set_mcp_revocation(args.tenant_id, revoked=True)}")
    if args.restore_mcp:
        print(f"mcp credentials restored: {await set_mcp_revocation(args.tenant_id, revoked=False)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
