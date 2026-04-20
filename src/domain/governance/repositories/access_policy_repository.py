from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
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

    async def get_default_policy_for_tenant(self, tenant_id: UUID) -> AccessPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(AccessPolicyModel).where(AccessPolicyModel.tenant_id == tenant_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.access_policy_repository.get_default_policy",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={"retriever_name": "get_default_policy_for_tenant"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalars().first()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

                return policy

    async def get_published_policy_version(
        self, access_policy_id: UUID
    ) -> AccessPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = (
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
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.access_policy_repository.get_published_version",
                input={
                    "query": query_sql,
                    "params": {"access_policy_id": str(access_policy_id)},
                },
                metadata={"retriever_name": "get_published_policy_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version = result.scalars().first()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version else 0,
                            "found": version is not None,
                        }
                    )

                return version

    async def create_policy(self, *, tenant_id: UUID, name: str) -> AccessPolicyModel:
        async with self.db.get_session() as session:
            instance = AccessPolicyModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_policy(self, *, access_policy_id: UUID) -> AccessPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(AccessPolicyModel).where(
                AccessPolicyModel.access_policy_id == access_policy_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_policies(self, *, tenant_id: UUID) -> list[AccessPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AccessPolicyModel)
                .where(AccessPolicyModel.tenant_id == tenant_id)
                .order_by(AccessPolicyModel.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_version(
        self,
        *,
        access_policy_id: UUID,
        rules: dict[str, object],
        status: str,
        version_major: int,
        version_minor: int,
        version_patch: int,
        config_hash: str | None = None,
    ) -> AccessPolicyVersionModel:
        async with self.db.get_session() as session:
            instance = AccessPolicyVersionModel(
                access_policy_id=access_policy_id,
                status=status,
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
                rules=rules,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_version(
        self, *, access_policy_version_id: UUID
    ) -> AccessPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = select(AccessPolicyVersionModel).where(
                AccessPolicyVersionModel.access_policy_version_id == access_policy_version_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_version_status(self, *, access_policy_version_id: UUID, status: str) -> None:
        async with self.db.get_session() as session:
            stmt = select(AccessPolicyVersionModel).where(
                AccessPolicyVersionModel.access_policy_version_id == access_policy_version_id
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if instance is None:
                return
            instance.status = status
            await session.commit()
