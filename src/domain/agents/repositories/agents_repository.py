from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.agent.active_agent_version import ActiveAgentVersion as ActiveAgentVersionModel
from infra.database.models.agent.agent import Agent as AgentModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel


class AgentsRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_agent(self, agent_id: UUID) -> AgentModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(select(AgentModel).where(AgentModel.agent_id == agent_id))
            return result.scalar_one_or_none()

    async def get_agent_version(self, agent_version_id: UUID) -> AgentVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentVersionModel).where(AgentVersionModel.agent_version_id == agent_version_id)
            )
            return result.scalar_one_or_none()

    async def set_agent_version_status(
        self, *, agent_version_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentVersionModel).where(AgentVersionModel.agent_version_id == agent_version_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            instance.status = str(status)
            await session.commit()

    async def get_active_agent_version_id(self, agent_id: UUID) -> UUID | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveAgentVersionModel).where(ActiveAgentVersionModel.agent_id == agent_id)
            )
            row = result.scalar_one_or_none()
            return row.agent_version_id if row else None

    async def upsert_active_agent_version(
        self,
        *,
        agent_id: UUID,
        agent_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveAgentVersionModel).where(ActiveAgentVersionModel.agent_id == agent_id)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    ActiveAgentVersionModel(
                        agent_id=agent_id,
                        agent_version_id=agent_version_id,
                        activated_by_principal_id=activated_by_principal_id,
                        justification=justification,
                    )
                )
            else:
                existing.agent_version_id = agent_version_id
                existing.activated_by_principal_id = activated_by_principal_id
                existing.justification = justification
            await session.commit()
