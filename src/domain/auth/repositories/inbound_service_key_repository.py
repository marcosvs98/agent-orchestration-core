from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database import DatabaseConnection
from infra.database.models.governance.tenant_inbound_service_key import (
    TenantInboundServiceKey,
)


class InboundServiceKeyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self._db = database_connection

    @staticmethod
    async def find_active_by_key_hash(
        session: AsyncSession,
        key_hash: str,
    ) -> TenantInboundServiceKey | None:
        stmt = (
            select(TenantInboundServiceKey)
            .where(TenantInboundServiceKey.key_hash == key_hash)
            .where(TenantInboundServiceKey.revoked_at.is_(None))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_for_tenant(
        session: AsyncSession,
        inbound_service_key_id: UUID,
        tenant_id: UUID,
    ) -> TenantInboundServiceKey | None:
        stmt = select(TenantInboundServiceKey).where(
            TenantInboundServiceKey.inbound_service_key_id == inbound_service_key_id,
            TenantInboundServiceKey.tenant_id == tenant_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert_key(
        self,
        tenant_id: UUID,
        key_hash: str,
    ) -> TenantInboundServiceKey:
        async with self._db.get_session() as session:
            row = TenantInboundServiceKey(tenant_id=tenant_id, key_hash=key_hash)
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row

    async def revoke_key(
        self,
        inbound_service_key_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        async with self._db.get_session() as session:
            row = await InboundServiceKeyRepository.get_by_id_for_tenant(
                session,
                inbound_service_key_id,
                tenant_id,
            )
            if row is None:
                return False
            if row.revoked_at is not None:
                return False
            row.revoked_at = datetime.now(timezone.utc)
            return True
