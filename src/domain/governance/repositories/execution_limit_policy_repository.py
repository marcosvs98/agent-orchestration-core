from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from infra.database import DatabaseConnection
from infra.database.models.governance.execution_limit_policy import (
    ExecutionLimitPolicy as ExecutionLimitPolicyModel,
)
from infra.database.models.governance.execution_limit_policy_version import (
    ExecutionLimitPolicyVersion as ExecutionLimitPolicyVersionModel,
)


class ExecutionLimitPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> ExecutionLimitPolicyModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ExecutionLimitPolicyModel).where(
                    ExecutionLimitPolicyModel.tenant_id == tenant_id
                )
            )
            return result.scalars().first()

    async def get_published_policy_version(
        self, execution_limit_policy_id: UUID
    ) -> ExecutionLimitPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ExecutionLimitPolicyVersionModel)
                .where(
                    ExecutionLimitPolicyVersionModel.execution_limit_policy_id
                    == execution_limit_policy_id
                )
                .where(ExecutionLimitPolicyVersionModel.status == VersionStatus.PUBLISHED)
                .order_by(
                    ExecutionLimitPolicyVersionModel.version_major.desc(),
                    ExecutionLimitPolicyVersionModel.version_minor.desc(),
                    ExecutionLimitPolicyVersionModel.version_patch.desc(),
                    ExecutionLimitPolicyVersionModel.created_at.desc(),
                )
            )
            return result.scalars().first()
