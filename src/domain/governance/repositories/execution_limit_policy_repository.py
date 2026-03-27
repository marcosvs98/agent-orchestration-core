from uuid import UUID, uuid4

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.governance.execution_limit_policy import (
    ExecutionLimitPolicy as ExecutionLimitPolicyModel,
)
from infra.database.models.governance.execution_limit_policy_version import (
    ExecutionLimitPolicyVersion as ExecutionLimitPolicyVersionModel,
)
from utils.query_compiler import compile_query


class ExecutionLimitPolicyRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_default_policy_for_tenant(
        self, tenant_id: UUID
    ) -> ExecutionLimitPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(ExecutionLimitPolicyModel).where(
                ExecutionLimitPolicyModel.tenant_id == tenant_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.execution_limit_policy_repository.get_default_policy",
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
        self, execution_limit_policy_id: UUID
    ) -> ExecutionLimitPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = (
                select(ExecutionLimitPolicyVersionModel)
                .where(
                    ExecutionLimitPolicyVersionModel.execution_limit_policy_id
                    == execution_limit_policy_id
                )
                .where(
                    ExecutionLimitPolicyVersionModel.status == VersionStatus.PUBLISHED
                )
                .order_by(
                    ExecutionLimitPolicyVersionModel.version_major.desc(),
                    ExecutionLimitPolicyVersionModel.version_minor.desc(),
                    ExecutionLimitPolicyVersionModel.version_patch.desc(),
                    ExecutionLimitPolicyVersionModel.created_at.desc(),
                )
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.execution_limit_policy_repository.get_published_version",
                input={
                    "query": query_sql,
                    "params": {
                        "execution_limit_policy_id": str(execution_limit_policy_id),
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

    async def list_policies_for_tenant(
        self, tenant_id: UUID, *, limit: int = 100
    ) -> list[ExecutionLimitPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(ExecutionLimitPolicyModel)
                .where(ExecutionLimitPolicyModel.tenant_id == tenant_id)
                .order_by(ExecutionLimitPolicyModel.created_at.desc())
                .limit(limit)
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.execution_limit_policy_repository.list_policies_for_tenant",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_policies_for_tenant"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                items = list(result.scalars().all())
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(items),
                            "found": len(items) > 0,
                        }
                    )
                return items

    async def ensure_default_published_policy_for_tenant(self, tenant_id: UUID) -> None:
        async with self.db.get_session() as session:
            policy_stmt = (
                select(ExecutionLimitPolicyModel)
                .where(ExecutionLimitPolicyModel.tenant_id == tenant_id)
                .order_by(ExecutionLimitPolicyModel.created_at.asc())
                .limit(1)
            )
            policy_result = await session.execute(policy_stmt)
            policy = policy_result.scalar_one_or_none()
            if policy is None:
                policy = ExecutionLimitPolicyModel(
                    execution_limit_policy_id=uuid4(),
                    tenant_id=tenant_id,
                    name="Default execution limits",
                )
                session.add(policy)
                await session.flush()
            pub_stmt = (
                select(ExecutionLimitPolicyVersionModel)
                .where(
                    ExecutionLimitPolicyVersionModel.execution_limit_policy_id
                    == policy.execution_limit_policy_id,
                    ExecutionLimitPolicyVersionModel.status == VersionStatus.PUBLISHED,
                )
                .limit(1)
            )
            pub_result = await session.execute(pub_stmt)
            if pub_result.scalar_one_or_none() is not None:
                await session.commit()
                return
            session.add(
                ExecutionLimitPolicyVersionModel(
                    execution_limit_policy_version_id=uuid4(),
                    execution_limit_policy_id=policy.execution_limit_policy_id,
                    status=VersionStatus.PUBLISHED,
                    version_major=1,
                    version_minor=0,
                    version_patch=0,
                )
            )
            await session.commit()
