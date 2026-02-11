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

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> RateLimitPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RateLimitPolicyModel).where(
                RateLimitPolicyModel.tenant_id == tenant_id
            )
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
