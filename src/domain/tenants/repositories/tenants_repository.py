from uuid import UUID

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.tenant import Tenant as TenantModel


class TenantsRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_tenant(self, tenant_id: UUID) -> TenantModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TenantModel).where(TenantModel.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def get_tenant_by_external_id(self, external_id: UUID) -> TenantModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TenantModel).where(TenantModel.external_id == external_id)
            )
            return result.scalar_one_or_none()

    async def create_tenant(self, *, tenant_data: dict) -> TenantModel:
        async with self.db.get_session() as session:
            instance = TenantModel(**tenant_data)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
