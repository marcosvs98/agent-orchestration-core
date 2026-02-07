from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.governance.access_policy import (
    AccessPolicy as AccessPolicyModel,
)
from infra.database.models.governance.access_policy_version import (
    AccessPolicyVersion as AccessPolicyVersionModel,
)


class AccessPolicyRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> AccessPolicyModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.access_policy_repository.get_default_policy",
            input={"tenant_id": str(tenant_id)},
        ):
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
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.access_policy_repository.get_published_version",
            input={"access_policy_id": str(access_policy_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AccessPolicyVersionModel)
                    .where(
                        AccessPolicyVersionModel.access_policy_id == access_policy_id
                    )
                    .where(AccessPolicyVersionModel.status == VersionStatus.PUBLISHED)
                    .order_by(
                        AccessPolicyVersionModel.version_major.desc(),
                        AccessPolicyVersionModel.version_minor.desc(),
                        AccessPolicyVersionModel.version_patch.desc(),
                        AccessPolicyVersionModel.created_at.desc(),
                    )
                )
                return result.scalars().first()
