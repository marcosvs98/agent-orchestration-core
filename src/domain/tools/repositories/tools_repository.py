from uuid import UUID

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from infra.database.models.agent.agent import Agent as AgentModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.tool.agent_version_tool_binding import (
    AgentVersionToolBinding as AgentVersionToolBindingModel,
)
from infra.database.models.tool.tool import Tool as ToolModel
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel


class ToolsRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_tool(self, tool_id: UUID) -> ToolModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolModel).where(ToolModel.tool_id == tool_id)
            )
            return result.scalar_one_or_none()

    async def get_tool_by_name(self, name: str) -> ToolModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolModel).where(ToolModel.name == name)
            )
            return result.scalar_one_or_none()

    async def create_tool(self, *, name: str | None, created_by: str) -> ToolModel:
        async with self.db.get_session() as session:
            instance = ToolModel(name=name)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_tools(
        self,
        *,
        tenant_id: UUID,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[ToolModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(ToolModel)
                .join(
                    ToolConfigModel, ToolModel.tool_id == ToolConfigModel.tool_id
                )
                .where(ToolConfigModel.tenant_id == tenant_id)
            )
            if status_filter:
                stmt = stmt.where(ToolConfigModel.status.in_(status_filter))
            stmt = stmt.distinct().order_by(ToolModel.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_tool_config(
        self, tool_config_id: UUID
    ) -> ToolConfigModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolConfigModel).where(
                    ToolConfigModel.tool_config_id == tool_config_id
                )
            )
            return result.scalar_one_or_none()

    async def list_tool_configs(
        self,
        *,
        tenant_id: UUID,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[ToolConfigModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(ToolConfigModel)
                .where(ToolConfigModel.tenant_id == tenant_id)
                .order_by(
                    ToolConfigModel.version_major.desc(),
                    ToolConfigModel.version_minor.desc(),
                    ToolConfigModel.version_patch.desc(),
                )
            )
            if status_filter:
                stmt = stmt.where(ToolConfigModel.status.in_(status_filter))
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_tool_config(
        self,
        *,
        tool_id: UUID,
        tenant_id: UUID,
        source_config_id: UUID | None = None,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        config: dict[str, object] | None = None,
        schema_version: int | None = None,
        created_by: str,
    ) -> ToolConfigModel:
        async with self.db.get_session() as session:
            if source_config_id is not None:
                source_config = await session.execute(
                    select(ToolConfigModel).where(
                        ToolConfigModel.tool_config_id == source_config_id
                    )
                )
                source = source_config.scalar_one_or_none()
                if source is None:
                    raise NotFoundServiceException(message="source_config_not_found")
                if version_major is None:
                    version_major = source.version_major
                if version_minor is None:
                    version_minor = source.version_minor
                if version_patch is None:
                    version_patch = source.version_patch + 1
                if config is None or config == {}:
                    config = source.config or {}
                if schema_version is None:
                    schema_version = source.schema_version

            if version_major is None or version_minor is None or version_patch is None:
                last_config = await session.execute(
                    select(ToolConfigModel)
                    .where(
                        ToolConfigModel.tool_id == tool_id,
                        ToolConfigModel.tenant_id == tenant_id,
                    )
                    .order_by(
                        ToolConfigModel.version_major.desc(),
                        ToolConfigModel.version_minor.desc(),
                        ToolConfigModel.version_patch.desc(),
                    )
                    .limit(1)
                )
                last = last_config.scalar_one_or_none()
                if last is None:
                    version_major = 1
                    version_minor = 0
                    version_patch = 0
                else:
                    if version_major is None:
                        version_major = last.version_major
                    if version_minor is None:
                        version_minor = last.version_minor
                    if version_patch is None:
                        version_patch = last.version_patch + 1

            instance = ToolConfigModel(
                tool_id=tool_id,
                tenant_id=tenant_id,
                status="DRAFT",
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config=config or {},
                schema_version=schema_version,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def set_tool_config_status(
        self, *, tool_config_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ToolConfigModel).where(
                    ToolConfigModel.tool_config_id == tool_config_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="tool_config_not_found")
            instance.status = str(status)
            await session.commit()

    async def create_agent_version_tool_binding(
        self,
        *,
        agent_version_id: UUID,
        tool_config_id: UUID,
        created_by: str,
    ) -> AgentVersionToolBindingModel:
        async with self.db.get_session() as session:
            agent_version = await session.execute(
                select(AgentVersionModel).where(
                    AgentVersionModel.agent_version_id == agent_version_id
                )
            )
            agent_version_instance = agent_version.scalar_one_or_none()
            if agent_version_instance is None:
                raise NotFoundServiceException(message="agent_version_not_found")

            agent = await session.execute(
                select(AgentModel).where(
                    AgentModel.agent_id == agent_version_instance.agent_id
                )
            )
            agent_instance = agent.scalar_one_or_none()
            if agent_instance is None:
                raise NotFoundServiceException(message="agent_not_found")

            tool_config = await session.execute(
                select(ToolConfigModel).where(
                    ToolConfigModel.tool_config_id == tool_config_id
                )
            )
            tool_config_instance = tool_config.scalar_one_or_none()
            if tool_config_instance is None:
                raise NotFoundServiceException(message="tool_config_not_found")

            if agent_instance.tenant_id != tool_config_instance.tenant_id:
                raise DomainValidationException(
                    message="agent_version_and_tool_config_must_belong_to_same_tenant"
                )

            instance = AgentVersionToolBindingModel(
                agent_version_id=agent_version_id, tool_config_id=tool_config_id
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
