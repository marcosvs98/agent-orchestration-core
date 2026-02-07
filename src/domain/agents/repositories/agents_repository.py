from uuid import UUID


from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from infra.database.models.agent.active_agent_version import (
    ActiveAgentVersion as ActiveAgentVersionModel,
)
from infra.database.models.agent.agent import Agent as AgentModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.agent.node_agent_binding import (
    NodeAgentBinding as NodeAgentBindingModel,
)
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel


class AgentsRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_agent(self, agent_id: UUID) -> AgentModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.get_agent",
            input={"agent_id": str(agent_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AgentModel).where(AgentModel.agent_id == agent_id)
                )
                return result.scalar_one_or_none()

    async def get_agent_version(
        self, agent_version_id: UUID
    ) -> AgentVersionModel | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.get_agent_version",
            input={"agent_version_id": str(agent_version_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(AgentVersionModel).where(
                        AgentVersionModel.agent_version_id == agent_version_id
                    )
                )
                return result.scalar_one_or_none()

    async def set_agent_version_status(
        self, *, agent_version_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version_status",
                input={"agent_version_id": str(agent_version_id)},
            ):
                result = await session.execute(
                    select(AgentVersionModel).where(
                        AgentVersionModel.agent_version_id == agent_version_id
                    )
                )
                instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            instance.status = str(status)
            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.agents_repository.set_agent_version_status",
                input={
                    "agent_version_id": str(agent_version_id),
                    "status": str(status),
                },
            ):
                await session.commit()

    async def get_active_agent_version_id(self, agent_id: UUID) -> UUID | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.get_active_agent_version_id",
            input={"agent_id": str(agent_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(ActiveAgentVersionModel).where(
                        ActiveAgentVersionModel.agent_id == agent_id
                    )
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
            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_existing_active_version",
                input={"agent_id": str(agent_id)},
            ):
                result = await session.execute(
                    select(ActiveAgentVersionModel).where(
                        ActiveAgentVersionModel.agent_id == agent_id
                    )
                )
                existing = result.scalar_one_or_none()
            if existing is None:
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.agents.agents_repository.create_active_version",
                    input={
                        "agent_id": str(agent_id),
                        "agent_version_id": str(agent_version_id),
                    },
                ):
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
            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.agents_repository.upsert_active_agent_version",
                input={"agent_id": str(agent_id)},
            ):
                await session.commit()

    async def list_agents(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[AgentModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.list_agents",
            input={"tenant_id": str(tenant_id), "limit": limit},
        ):
            async with self.db.get_session() as session:
                stmt = (
                    select(AgentModel)
                    .where(AgentModel.tenant_id == tenant_id)
                    .order_by(AgentModel.created_at.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())

    async def create_agent(
        self, *, tenant_id: UUID, name: str | None, created_by: str
    ) -> AgentModel:
        with self.tracer.observe(
            as_type="tool",
            name="domain.agents.agents_repository.create_agent",
            input={"tenant_id": str(tenant_id), "name": name},
        ):
            async with self.db.get_session() as session:
                instance = AgentModel(tenant_id=tenant_id, name=name)
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def list_agent_versions(
        self, *, agent_id: UUID, status_filter: list[str] | None = None
    ) -> list[AgentVersionModel]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.list_agent_versions",
            input={"agent_id": str(agent_id)},
        ):
            async with self.db.get_session() as session:
                stmt = (
                    select(AgentVersionModel)
                    .where(AgentVersionModel.agent_id == agent_id)
                    .order_by(
                        AgentVersionModel.version_major.desc(),
                        AgentVersionModel.version_minor.desc(),
                        AgentVersionModel.version_patch.desc(),
                    )
                )
                if status_filter:
                    stmt = stmt.where(AgentVersionModel.status.in_(status_filter))
                result = await session.execute(stmt)
                return list(result.scalars().all())

    async def create_agent_version(
        self,
        *,
        agent_id: UUID,
        source_version_id: UUID | None = None,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        description: str | None = None,
        supported_tool_schema_version: int | None = None,
        supported_tool_config_hash_prefix: str | None = None,
        persona_config: dict | None = None,
        created_by: str,
    ) -> AgentVersionModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.agents.agents_repository.get_source_version",
                    input={"source_version_id": str(source_version_id)},
                ):
                    source_version = await session.execute(
                        select(AgentVersionModel).where(
                            AgentVersionModel.agent_version_id == source_version_id
                        )
                    )
                    source = source_version.scalar_one_or_none()
                if source is None:
                    raise NotFoundServiceException(message="source_version_not_found")
                if version_major is None:
                    version_major = source.version_major
                if version_minor is None:
                    version_minor = source.version_minor
                if version_patch is None:
                    version_patch = source.version_patch + 1
                if description is None:
                    description = source.description
                if supported_tool_schema_version is None:
                    supported_tool_schema_version = source.supported_tool_schema_version
                if supported_tool_config_hash_prefix is None:
                    supported_tool_config_hash_prefix = (
                        source.supported_tool_config_hash_prefix
                    )
                if persona_config is None:
                    persona_config = source.persona_config

            if version_major is None or version_minor is None or version_patch is None:
                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.agents.agents_repository.get_last_version",
                    input={"agent_id": str(agent_id)},
                ):
                    last_version = await session.execute(
                        select(AgentVersionModel)
                        .where(AgentVersionModel.agent_id == agent_id)
                        .order_by(
                            AgentVersionModel.version_major.desc(),
                            AgentVersionModel.version_minor.desc(),
                            AgentVersionModel.version_patch.desc(),
                        )
                        .limit(1)
                    )
                    last = last_version.scalar_one_or_none()
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

            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.agents_repository.create_agent_version",
                input={"agent_id": str(agent_id)},
            ):
                instance = AgentVersionModel(
                    agent_id=agent_id,
                    status=VersionStatus.DRAFT.value,
                    version_major=version_major,
                    version_minor=version_minor,
                    version_patch=version_patch,
                    description=description,
                    supported_tool_schema_version=supported_tool_schema_version,
                    supported_tool_config_hash_prefix=supported_tool_config_hash_prefix,
                    persona_config=persona_config,
                )
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def create_node_agent_binding(
        self, *, node_id: UUID, agent_version_id: UUID, created_by: str
    ) -> NodeAgentBindingModel:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_node_binding",
                input={"node_id": str(node_id)},
            ):
                node = await session.execute(
                    select(NodeModel).where(NodeModel.node_id == node_id)
                )
                node_instance = node.scalar_one_or_none()
            if node_instance is None:
                raise NotFoundServiceException(message="node_not_found")

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version_binding",
                input={"agent_version_id": str(agent_version_id)},
            ):
                agent_version = await session.execute(
                    select(AgentVersionModel).where(
                        AgentVersionModel.agent_version_id == agent_version_id
                    )
                )
                agent_version_instance = agent_version.scalar_one_or_none()
            if agent_version_instance is None:
                raise NotFoundServiceException(message="agent_version_not_found")

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_flow_version_binding",
                input={"flow_version_id": str(node_instance.flow_version_id)},
            ):
                flow_version = await session.execute(
                    select(FlowVersionModel).where(
                        FlowVersionModel.flow_version_id
                        == node_instance.flow_version_id
                    )
                )
                flow_version_instance = flow_version.scalar_one_or_none()
            if flow_version_instance is None:
                raise NotFoundServiceException(message="flow_version_not_found")

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_flow_binding",
                input={"flow_id": str(flow_version_instance.flow_id)},
            ):
                flow = await session.execute(
                    select(FlowModel).where(
                        FlowModel.flow_id == flow_version_instance.flow_id
                    )
                )
                flow_instance = flow.scalar_one_or_none()
            if flow_instance is None:
                raise NotFoundServiceException(message="flow_not_found")

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_binding",
                input={"agent_id": str(agent_version_instance.agent_id)},
            ):
                agent = await session.execute(
                    select(AgentModel).where(
                        AgentModel.agent_id == agent_version_instance.agent_id
                    )
                )
                agent_instance = agent.scalar_one_or_none()
            if agent_instance is None:
                raise NotFoundServiceException(message="agent_not_found")

            if flow_instance.tenant_id != agent_instance.tenant_id:
                raise DomainValidationException(
                    message="node_and_agent_must_belong_to_same_tenant"
                )

            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.agents_repository.create_node_agent_binding",
                input={
                    "node_id": str(node_id),
                    "agent_version_id": str(agent_version_id),
                },
            ):
                instance = NodeAgentBindingModel(
                    node_id=node_id, agent_version_id=agent_version_id
                )
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def get_agent_version_id_by_node_id(self, node_id: UUID) -> UUID | None:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.agents.agents_repository.get_agent_version_id_by_node_id",
            input={"node_id": str(node_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(NodeAgentBindingModel).where(
                        NodeAgentBindingModel.node_id == node_id
                    )
                )
                binding = result.scalar_one_or_none()
                return binding.agent_version_id if binding else None
