from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.governance.runtime_policy import (
    RuntimePolicy as RuntimePolicyModel,
)


class RuntimePolicyRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def create_policy(
        self,
        *,
        tenant_id: UUID,
        scope: str,
        flow_id: UUID | None,
        policy_definition: dict,
        created_by: str,
        version: str = "1",
        status: str = "DRAFT",
    ) -> RuntimePolicyModel:
        with self.tracer.observe(
            as_type="tool",
            name="domain.governance.runtime_policy_repository.create_policy",
            input={"tenant_id": str(tenant_id), "scope": scope},
        ):
            async with self.db.get_session() as session:
                instance = RuntimePolicyModel(
                    tenant_id=tenant_id,
                    scope=scope,
                    flow_id=flow_id,
                    version=version,
                    status=status,
                    policy_definition=policy_definition,
                    created_by=created_by,
                )
                session.add(instance)
                await session.commit()
                return instance

    async def activate_policy(
        self, runtime_policy_id: UUID, principal_id: str
    ) -> RuntimePolicyModel:
        async with self.db.get_session() as session:
            stmt = select(RuntimePolicyModel).where(
                RuntimePolicyModel.runtime_policy_id == runtime_policy_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.runtime_policy_repository.get_for_activation",
                input={
                    "query": query_sql,
                    "params": {"runtime_policy_id": str(runtime_policy_id)},
                },
                metadata={"retriever_name": "get_for_activation"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="runtime_policy_not_found")
            with self.tracer.observe(
                as_type="tool",
                name="domain.governance.runtime_policy_repository.deactivate_scope",
                input={"tenant_id": str(instance.tenant_id), "scope": instance.scope},
            ):
                await session.execute(
                    sa.update(RuntimePolicyModel)
                    .where(
                        RuntimePolicyModel.tenant_id == instance.tenant_id,
                        RuntimePolicyModel.scope == instance.scope,
                        RuntimePolicyModel.flow_id == instance.flow_id,
                        RuntimePolicyModel.status == "ACTIVE",
                    )
                    .values(status="DRAFT")
                )
            instance.status = "ACTIVE"
            with self.tracer.observe(
                as_type="tool",
                name="domain.governance.runtime_policy_repository.activate_policy",
                input={"runtime_policy_id": str(runtime_policy_id)},
            ):
                await session.commit()
            return instance

    async def get_active_flow_policy(
        self, tenant_id: UUID, flow_id: UUID
    ) -> RuntimePolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RuntimePolicyModel).where(
                RuntimePolicyModel.tenant_id == tenant_id,
                RuntimePolicyModel.scope == "FLOW",
                RuntimePolicyModel.flow_id == flow_id,
                RuntimePolicyModel.status == "ACTIVE",
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.runtime_policy_repository.get_active_flow_policy",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "flow_id": str(flow_id),
                    },
                },
                metadata={"retriever_name": "get_active_flow_policy"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

                return policy

    async def get_active_tenant_policy(
        self, tenant_id: UUID
    ) -> RuntimePolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RuntimePolicyModel).where(
                RuntimePolicyModel.tenant_id == tenant_id,
                RuntimePolicyModel.scope == "TENANT",
                RuntimePolicyModel.status == "ACTIVE",
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.runtime_policy_repository.get_active_tenant_policy",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={"retriever_name": "get_active_tenant_policy"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

                return policy

    async def list_policies(self, tenant_id: UUID) -> list[RuntimePolicyModel]:
        async with self.db.get_session() as session:
            stmt = select(RuntimePolicyModel).where(
                RuntimePolicyModel.tenant_id == tenant_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.runtime_policy_repository.list_policies",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={"retriever_name": "list_policies"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policies = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(policies),
                            "found": len(policies) > 0,
                        }
                    )

                return policies
