from uuid import UUID

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.access_policy import (
    AccessPolicy as AccessPolicyModel,
)
from infra.database.models.governance.access_policy_version import (
    AccessPolicyVersion as AccessPolicyVersionModel,
)
from domain.common.schemas.versioning import VersionStatus


class AccessPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> AccessPolicyModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AccessPolicyModel).where(
                    AccessPolicyModel.tenant_id == tenant_id
                )
            )
            return result.scalars().first()

    async def get_published_policy_version(
        self, access_policy_id: UUID
    ) -> AccessPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AccessPolicyVersionModel)
                .where(AccessPolicyVersionModel.access_policy_id == access_policy_id)
                .where(AccessPolicyVersionModel.status == VersionStatus.PUBLISHED)
                .order_by(
                    AccessPolicyVersionModel.version_major.desc(),
                    AccessPolicyVersionModel.version_minor.desc(),
                    AccessPolicyVersionModel.version_patch.desc(),
                    AccessPolicyVersionModel.created_at.desc(),
                )
            )
            return result.scalars().first()
