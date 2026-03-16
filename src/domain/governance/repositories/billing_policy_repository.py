from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.active_billing_policy_version import (
    ActiveBillingPolicyVersion as ActiveBillingPolicyVersionModel,
)
from infra.database.models.governance.billing_policy import (
    BillingPolicy as BillingPolicyModel,
)
from infra.database.models.governance.billing_policy_version import (
    BillingPolicyVersion as BillingPolicyVersionModel,
)


class BillingPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def create_policy(self, *, tenant_id: UUID, name: str) -> BillingPolicyModel:
        async with self.db.get_session() as session:
            instance = BillingPolicyModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_policies(self, *, tenant_id: UUID) -> list[BillingPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(BillingPolicyModel)
                .where(BillingPolicyModel.tenant_id == tenant_id)
                .order_by(BillingPolicyModel.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_policy(self, *, billing_policy_id: UUID) -> BillingPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(BillingPolicyModel).where(
                BillingPolicyModel.billing_policy_id == billing_policy_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_version(
        self,
        *,
        billing_policy_id: UUID,
        status: str,
        version_major: int,
        version_minor: int,
        version_patch: int,
        rules: dict[str, object],
        config_hash: str | None = None,
    ) -> BillingPolicyVersionModel:
        async with self.db.get_session() as session:
            instance = BillingPolicyVersionModel(
                billing_policy_id=billing_policy_id,
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
        self, *, billing_policy_version_id: UUID
    ) -> BillingPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = select(BillingPolicyVersionModel).where(
                BillingPolicyVersionModel.billing_policy_version_id
                == billing_policy_version_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_version_status(
        self, *, billing_policy_version_id: UUID, status: str
    ) -> None:
        async with self.db.get_session() as session:
            stmt = select(BillingPolicyVersionModel).where(
                BillingPolicyVersionModel.billing_policy_version_id
                == billing_policy_version_id
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if instance is None:
                return
            instance.status = status
            await session.commit()

    async def set_active_version(
        self,
        *,
        tenant_id: UUID,
        billing_policy_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
    ) -> ActiveBillingPolicyVersionModel:
        async with self.db.get_session() as session:
            stmt = select(ActiveBillingPolicyVersionModel).where(
                ActiveBillingPolicyVersionModel.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            active = result.scalar_one_or_none()
            if active is None:
                active = ActiveBillingPolicyVersionModel(
                    tenant_id=tenant_id,
                    billing_policy_version_id=billing_policy_version_id,
                    activated_by_principal_id=activated_by_principal_id,
                    justification=justification,
                )
                session.add(active)
            else:
                active.billing_policy_version_id = billing_policy_version_id
                active.activated_by_principal_id = activated_by_principal_id
                active.justification = justification
            await session.commit()
            await session.refresh(active)
            return active
