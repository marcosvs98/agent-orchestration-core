from uuid import UUID


from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.governance.rate_limit_policy import (
    RateLimitPolicy as RateLimitPolicyModel,
)
from infra.database.models.governance.rate_limit_policy_version import (
    RateLimitPolicyVersion as RateLimitPolicyVersionModel,
)
from utils.query_compiler import compile_query


class RateLimitPolicyRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_default_policy_for_tenant(self, tenant_id: UUID) -> RateLimitPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RateLimitPolicyModel).where(RateLimitPolicyModel.tenant_id == tenant_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.rate_limit_policy_repository.get_default_policy",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={"retriever_name": "get_default_policy"},
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
        self, rate_limit_policy_id: UUID, *, action: str, principal_type: str
    ) -> RateLimitPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = (
                select(RateLimitPolicyVersionModel)
                .where(RateLimitPolicyVersionModel.rate_limit_policy_id == rate_limit_policy_id)
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
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.rate_limit_policy_repository.get_published_version",
                input={
                    "query": query_sql,
                    "params": {
                        "rate_limit_policy_id": str(rate_limit_policy_id),
                        "action": action,
                        "principal_type": principal_type,
                    },
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

    async def create_policy(self, *, tenant_id: UUID, name: str) -> RateLimitPolicyModel:
        async with self.db.get_session() as session:
            instance = RateLimitPolicyModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_policies(self, *, tenant_id: UUID) -> list[RateLimitPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RateLimitPolicyModel)
                .where(RateLimitPolicyModel.tenant_id == tenant_id)
                .order_by(RateLimitPolicyModel.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_policy(self, *, rate_limit_policy_id: UUID) -> RateLimitPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RateLimitPolicyModel).where(
                RateLimitPolicyModel.rate_limit_policy_id == rate_limit_policy_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_version(
        self,
        *,
        rate_limit_policy_id: UUID,
        status: str,
        version_major: int,
        version_minor: int,
        version_patch: int,
        action: str,
        principal_type: str,
        limit: int,
        window_seconds: int,
        config_hash: str | None = None,
    ) -> RateLimitPolicyVersionModel:
        async with self.db.get_session() as session:
            instance = RateLimitPolicyVersionModel(
                rate_limit_policy_id=rate_limit_policy_id,
                status=status,
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
                action=action,
                principal_type=principal_type,
                limit=limit,
                window_seconds=window_seconds,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_version(
        self, *, rate_limit_policy_version_id: UUID
    ) -> RateLimitPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = select(RateLimitPolicyVersionModel).where(
                RateLimitPolicyVersionModel.rate_limit_policy_version_id
                == rate_limit_policy_version_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_version_status(self, *, rate_limit_policy_version_id: UUID, status: str) -> None:
        async with self.db.get_session() as session:
            stmt = select(RateLimitPolicyVersionModel).where(
                RateLimitPolicyVersionModel.rate_limit_policy_version_id
                == rate_limit_policy_version_id
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if instance is None:
                return
            instance.status = status
            await session.commit()
