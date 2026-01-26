from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from infra.database import DatabaseConnection
from infra.database.models.governance.rate_limit_policy import (
    RateLimitPolicy as RateLimitPolicyModel,
)
from infra.database.models.governance.rate_limit_policy_version import (
    RateLimitPolicyVersion as RateLimitPolicyVersionModel,
)


class RateLimitPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> RateLimitPolicyModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RateLimitPolicyModel).where(
                    RateLimitPolicyModel.tenant_id == tenant_id
                )
            )
            return result.scalars().first()

    async def get_published_policy_version(
        self, rate_limit_policy_id: UUID, *, action: str, principal_type: str
    ) -> RateLimitPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RateLimitPolicyVersionModel)
                .where(
                    RateLimitPolicyVersionModel.rate_limit_policy_id
                    == rate_limit_policy_id
                )
                .where(RateLimitPolicyVersionModel.status == VersionStatus.PUBLISHED)
                .where(RateLimitPolicyVersionModel.action == action)
                .where(RateLimitPolicyVersionModel.principal_type == principal_type)
                .order_by(
                    RateLimitPolicyVersionModel.version_major.desc(),
                    RateLimitPolicyVersionModel.version_minor.desc(),
                    RateLimitPolicyVersionModel.version_patch.desc(),
                    RateLimitPolicyVersionModel.created_at.desc(),
                )
            )
            return result.scalars().first()
