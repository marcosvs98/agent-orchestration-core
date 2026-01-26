from uuid import UUID, uuid4

from sqlalchemy import select

from infra.database import DatabaseConnection
from infra.database.models.governance.authoring_event import (
    AuthoringEvent as AuthoringEventModel,
)


class AuthoringEventRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def append_event(
        self,
        *,
        tenant_id: UUID,
        resource_type: str,
        resource_id: UUID,
        version_id: UUID | None,
        event_type: str,
        change_type: str,
        principal_id: str,
        justification: str,
        schema_version: int = 1,
    ) -> UUID:
        event_id = uuid4()
        async with self.db.get_session() as session:
            session.add(
                AuthoringEventModel(
                    authoring_event_id=event_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    version_id=version_id,
                    event_type=event_type,
                    change_type=change_type,
                    principal_id=principal_id,
                    justification=justification,
                    schema_version=schema_version,
                )
            )
            await session.commit()
        return event_id

    async def list_events_for_resource(
        self, *, tenant_id: UUID, resource_type: str, resource_id: UUID
    ) -> list[AuthoringEventModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AuthoringEventModel)
                .where(AuthoringEventModel.tenant_id == tenant_id)
                .where(AuthoringEventModel.resource_type == resource_type)
                .where(AuthoringEventModel.resource_id == resource_id)
                .order_by(AuthoringEventModel.occurred_at.asc())
            )
            return list(result.scalars().all())
