from uuid import UUID

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.tenant_mcp_credential import TenantMcpCredential


class TenantMcpCredentialRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self._db = database_connection

    async def find_active_for_tenant(self, *, tenant_id: UUID) -> TenantMcpCredential | None:
        async with self._db.get_session() as session:
            stmt = (
                select(TenantMcpCredential)
                .where(
                    TenantMcpCredential.tenant_id == tenant_id,
                    TenantMcpCredential.revoked_at.is_(None),
                )
                .order_by(TenantMcpCredential.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
