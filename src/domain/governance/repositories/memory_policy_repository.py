from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.active_memory_policy_version import (
    ActiveMemoryPolicyVersion as ActiveMemoryPolicyVersionModel,
)
from infra.database.models.governance.memory_policy import (
    MemoryPolicy as MemoryPolicyModel,
)
from infra.database.models.governance.memory_policy_version import (
    MemoryPolicyVersion as MemoryPolicyVersionModel,
)


class MemoryPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def create_policy(self, *, tenant_id: UUID, name: str) -> MemoryPolicyModel:
        async with self.db.get_session() as session:
            instance = MemoryPolicyModel(tenant_id=tenant_id, name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_policies(self, *, tenant_id: UUID) -> list[MemoryPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(MemoryPolicyModel)
                .where(MemoryPolicyModel.tenant_id == tenant_id)
                .order_by(MemoryPolicyModel.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_policy(self, *, memory_policy_id: UUID) -> MemoryPolicyModel | None:
        async with self.db.get_session() as session:
            stmt = select(MemoryPolicyModel).where(
                MemoryPolicyModel.memory_policy_id == memory_policy_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_version(
        self,
        *,
        memory_policy_id: UUID,
        status: str,
        version_major: int,
        version_minor: int,
        version_patch: int,
        retention_ttl_seconds: int,
        consent_definition: dict[str, object],
        allowed_sources: list[object],
        allowed_schemas: list[dict[str, object]],
        config_hash: str | None = None,
    ) -> MemoryPolicyVersionModel:
        async with self.db.get_session() as session:
            instance = MemoryPolicyVersionModel(
                memory_policy_id=memory_policy_id,
                status=status,
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
                retention_ttl_seconds=retention_ttl_seconds,
                consent_definition=consent_definition,
                allowed_sources=allowed_sources,
                allowed_schemas=allowed_schemas,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_version(
        self, *, memory_policy_version_id: UUID
    ) -> MemoryPolicyVersionModel | None:
        async with self.db.get_session() as session:
            stmt = select(MemoryPolicyVersionModel).where(
                MemoryPolicyVersionModel.memory_policy_version_id
                == memory_policy_version_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_version_status(
        self, *, memory_policy_version_id: UUID, status: str
    ) -> None:
        async with self.db.get_session() as session:
            stmt = select(MemoryPolicyVersionModel).where(
                MemoryPolicyVersionModel.memory_policy_version_id
                == memory_policy_version_id
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
        memory_policy_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
    ) -> ActiveMemoryPolicyVersionModel:
        async with self.db.get_session() as session:
            stmt = select(ActiveMemoryPolicyVersionModel).where(
                ActiveMemoryPolicyVersionModel.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            active = result.scalar_one_or_none()
            if active is None:
                active = ActiveMemoryPolicyVersionModel(
                    tenant_id=tenant_id,
                    memory_policy_version_id=memory_policy_version_id,
                    activated_by_principal_id=activated_by_principal_id,
                    justification=justification,
                )
                session.add(active)
            else:
                active.memory_policy_version_id = memory_policy_version_id
                active.activated_by_principal_id = activated_by_principal_id
                active.justification = justification
            await session.commit()
            await session.refresh(active)
            return active
