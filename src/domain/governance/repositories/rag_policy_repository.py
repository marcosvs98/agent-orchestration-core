from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from datetime import datetime, timezone

from infra.database import DatabaseConnection
from infra.database.models.governance.rag_policy import RagPolicy as RagPolicyModel
from infra.database.models.governance.rag_policy_version import (
    RagPolicyVersion as RagPolicyVersionModel,
)


class RagPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def create_policy(self, *, tenant_id: UUID, name: str) -> RagPolicyModel:
        async with self.db.get_session() as session:
            instance = RagPolicyModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_policies(self, *, tenant_id: UUID) -> list[RagPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RagPolicyModel)
                .where(RagPolicyModel.tenant_id == tenant_id)
                .order_by(RagPolicyModel.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_policy(self, *, rag_policy_id: UUID) -> RagPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(RagPolicyModel).where(RagPolicyModel.rag_policy_id == rag_policy_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_version(
        self,
        *,
        rag_policy_id: UUID,
        status: str,
        version_major: int,
        version_minor: int,
        version_patch: int,
        policy_definition: dict[str, object],
        config_hash: str | None = None,
    ) -> RagPolicyVersionModel:
        async with self.db.get_session() as session:
            instance = RagPolicyVersionModel(
                rag_policy_id=rag_policy_id,
                status=status,
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
                policy_definition=policy_definition,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_version(self, *, rag_policy_version_id: UUID) -> RagPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = select(RagPolicyVersionModel).where(
                RagPolicyVersionModel.rag_policy_version_id == rag_policy_version_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_version_status(self, *, rag_policy_version_id: UUID, status: str) -> None:
        async with self.db.get_session() as session:
            stmt = select(RagPolicyVersionModel).where(
                RagPolicyVersionModel.rag_policy_version_id == rag_policy_version_id
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
        rag_policy_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
    ) -> RagPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RagPolicyVersionModel).where(
                    RagPolicyVersionModel.tenant_id == tenant_id,
                    RagPolicyVersionModel.is_active.is_(True),
                )
            )
            for row in result.scalars().all():
                row.is_active = False

            stmt = select(RagPolicyVersionModel).where(
                RagPolicyVersionModel.rag_policy_version_id == rag_policy_version_id
            )
            target = (await session.execute(stmt)).scalar_one_or_none()
            if target is None:
                return None
            target.tenant_id = tenant_id
            target.is_active = True
            target.activated_at = datetime.now(timezone.utc)
            target.activated_by_principal_id = activated_by_principal_id
            target.justification = justification
            await session.commit()
            await session.refresh(target)
            return target
