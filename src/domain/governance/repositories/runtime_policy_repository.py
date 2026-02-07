from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
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
            with self.tracer.observe(
                as_type="retriever",
                name="domain.governance.runtime_policy_repository.get_for_activation",
                input={"runtime_policy_id": str(runtime_policy_id)},
            ):
                result = await session.execute(
                    select(RuntimePolicyModel).where(
                        RuntimePolicyModel.runtime_policy_id == runtime_policy_id
                    )
                )
                instance = result.scalar_one_or_none()
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
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.runtime_policy_repository.get_active_flow_policy",
            input={"tenant_id": str(tenant_id), "flow_id": str(flow_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(RuntimePolicyModel).where(
                        RuntimePolicyModel.tenant_id == tenant_id,
                        RuntimePolicyModel.scope == "FLOW",
                        RuntimePolicyModel.flow_id == flow_id,
                        RuntimePolicyModel.status == "ACTIVE",
                    )
                )
                return result.scalar_one_or_none()

    async def get_active_tenant_policy(
        self, tenant_id: UUID
    ) -> RuntimePolicyModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.runtime_policy_repository.get_active_tenant_policy",
            input={"tenant_id": str(tenant_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(RuntimePolicyModel).where(
                        RuntimePolicyModel.tenant_id == tenant_id,
                        RuntimePolicyModel.scope == "TENANT",
                        RuntimePolicyModel.status == "ACTIVE",
                    )
                )
                return result.scalar_one_or_none()

    async def list_policies(self, tenant_id: UUID) -> list[RuntimePolicyModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.governance.runtime_policy_repository.list_policies",
            input={"tenant_id": str(tenant_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(RuntimePolicyModel).where(
                        RuntimePolicyModel.tenant_id == tenant_id
                    )
                )
                return list(result.scalars().all())
