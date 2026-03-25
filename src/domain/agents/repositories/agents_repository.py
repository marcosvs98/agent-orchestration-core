from uuid import UUID

from sqlalchemy import func, select

from adapters.cache.redis_adapter import RedisAdapter
from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from infra.database.models.agent.agent import Agent as AgentModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.agent.node_agent_binding import (
    NodeAgentBinding as NodeAgentBindingModel,
)
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from utils.query_compiler import compile_query


AGENT_VERSION_BY_NODE_CACHE_TTL = 3600


class AgentsRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_agent(self, agent_id: UUID) -> AgentModel | None:
        async with self.db.get_session() as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent",
                input={
                    "query": query_sql,
                    "params": {"agent_id": str(agent_id)},
                },
                metadata={"retriever_name": "get_agent"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                agent = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if agent else 0,
                            "found": agent is not None,
                        }
                    )
                return agent

    async def get_agent_version(
        self, agent_version_id: UUID
    ) -> AgentVersionModel | None:
        key = f"agent_version_by_id:{agent_version_id}"
        if cached := await self.cache_adapter.get(key):
            return AgentVersionModel(**cached)

        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version",
                input={
                    "query": query_sql,
                    "params": {"agent_version_id": str(agent_version_id)},
                },
                metadata={"retriever_name": "get_agent_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version else 0,
                            "found": version is not None,
                            "origem": "database"
                        }
                    )
                await self.cache_adapter.set(key, version.to_dict())

                return version

    async def set_agent_version_status(
        self, *, agent_version_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version_status",
                input={
                    "query": query_sql,
                    "params": {"agent_version_id": str(agent_version_id)},
                },
                metadata={"retriever_name": "get_agent_version_status"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

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
        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel.agent_version_id).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_active_agent_version_id",
                input={
                    "query": query_sql,
                    "params": {"agent_id": str(agent_id)},
                },
                metadata={"retriever_name": "get_active_agent_version_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

                return version_id

    async def upsert_active_agent_version(
        self,
        *,
        agent_id: UUID,
        agent_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
    ) -> None:
        from datetime import datetime, timezone

        async with self.db.get_session() as session:
            deactivate = select(AgentVersionModel).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.is_active.is_(True),
            )
            result = await session.execute(deactivate)
            for row in result.scalars().all():
                row.is_active = False

            stmt = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id,
                AgentVersionModel.agent_id == agent_id,
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_existing_active_version",
                input={"query": query_sql, "params": {"agent_id": str(agent_id)}},
                metadata={"retriever_name": "get_existing_active_version"},
            ) as retriever_handle:
                res = await session.execute(stmt)
                target = res.scalar_one_or_none()
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if target else 0,
                            "found": target is not None,
                        }
                    )

            if target is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            target.is_active = True
            target.activated_at = datetime.now(timezone.utc)
            target.activated_by_principal_id = activated_by_principal_id
            target.justification = justification
            with self.tracer.observe(
                as_type="tool",
                name="domain.agents.agents_repository.upsert_active_agent_version",
                input={"agent_id": str(agent_id)},
            ):
                await session.commit()

    async def list_agents(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[AgentModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentModel)
                .where(AgentModel.tenant_id == tenant_id)
                .order_by(AgentModel.created_at.desc())
                .limit(limit)
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.list_agents",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_agents"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                items = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(items),
                            "found": len(items) > 0,
                        }
                    )

                return items

    async def count_active_agent_versions(self, tenant_id: UUID) -> int:
        async with self.db.get_session() as session:
            stmt = (
                select(func.count(AgentVersionModel.agent_version_id))
                .join(AgentModel, AgentVersionModel.agent_id == AgentModel.agent_id)
                .where(
                    AgentModel.tenant_id == tenant_id,
                    AgentVersionModel.is_active.is_(True),
                )
            )
            result = await session.execute(stmt)
            value = result.scalar()
            return int(value) if value is not None else 0

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
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.list_agent_versions",
                input={
                    "query": query_sql,
                    "params": {
                        "agent_id": str(agent_id),
                        "status_filter": status_filter,
                    },
                },
                metadata={"retriever_name": "list_agent_versions"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                items = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(items),
                            "found": len(items) > 0,
                        }
                    )

                return items

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
        system_prompt: str | None = None,
        created_by: str,
    ) -> AgentVersionModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                stmt_source = select(AgentVersionModel).where(
                    AgentVersionModel.agent_version_id == source_version_id
                )
                query_sql_source = compile_query(stmt_source)

                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.agents.agents_repository.get_source_version",
                    input={
                        "query": query_sql_source,
                        "params": {"source_version_id": str(source_version_id)},
                    },
                    metadata={"retriever_name": "get_source_version"},
                ) as retriever_handle:
                    source_version = await session.execute(stmt_source)
                    source = source_version.scalar_one_or_none()

                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if source else 0,
                                "found": source is not None,
                            }
                        )

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
                if system_prompt is None:
                    system_prompt = source.system_prompt

            if version_major is None or version_minor is None or version_patch is None:
                stmt_last = (
                    select(AgentVersionModel)
                    .where(AgentVersionModel.agent_id == agent_id)
                    .order_by(
                        AgentVersionModel.version_major.desc(),
                        AgentVersionModel.version_minor.desc(),
                        AgentVersionModel.version_patch.desc(),
                    )
                    .limit(1)
                )
                query_sql_last = compile_query(stmt_last)

                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.agents.agents_repository.get_last_version",
                    input={
                        "query": query_sql_last,
                        "params": {"agent_id": str(agent_id)},
                    },
                    metadata={"retriever_name": "get_last_version"},
                ) as retriever_handle:
                    last_version = await session.execute(stmt_last)
                    last = last_version.scalar_one_or_none()

                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if last else 0,
                                "found": last is not None,
                            }
                        )

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
                    system_prompt=system_prompt,
                )
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def create_node_agent_binding(
        self, *, node_id: UUID, agent_version_id: UUID, created_by: str
    ) -> NodeAgentBindingModel:
        async with self.db.get_session() as session:
            stmt_node = select(NodeModel).where(NodeModel.node_id == node_id)
            query_sql_node = compile_query(stmt_node)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_node_binding",
                input={
                    "query": query_sql_node,
                    "params": {"node_id": str(node_id)},
                },
                metadata={"retriever_name": "get_node_binding"},
            ) as retriever_handle:
                node = await session.execute(stmt_node)
                node_instance = node.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if node_instance else 0,
                            "found": node_instance is not None,
                        }
                    )

            if node_instance is None:
                raise NotFoundServiceException(message="node_not_found")

            stmt_av = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id
            )
            query_sql_av = compile_query(stmt_av)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version_binding",
                input={
                    "query": query_sql_av,
                    "params": {"agent_version_id": str(agent_version_id)},
                },
                metadata={"retriever_name": "get_agent_version_binding"},
            ) as retriever_handle:
                agent_version = await session.execute(stmt_av)
                agent_version_instance = agent_version.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if agent_version_instance else 0,
                            "found": agent_version_instance is not None,
                        }
                    )

            if agent_version_instance is None:
                raise NotFoundServiceException(message="agent_version_not_found")

            stmt_fv = select(FlowVersionModel).where(
                FlowVersionModel.flow_version_id == node_instance.flow_version_id
            )
            query_sql_fv = compile_query(stmt_fv)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_flow_version_binding",
                input={
                    "query": query_sql_fv,
                    "params": {
                        "flow_version_id": str(node_instance.flow_version_id),
                    },
                },
                metadata={"retriever_name": "get_flow_version_binding"},
            ) as retriever_handle:
                flow_version = await session.execute(stmt_fv)
                flow_version_instance = flow_version.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow_version_instance else 0,
                            "found": flow_version_instance is not None,
                        }
                    )

            if flow_version_instance is None:
                raise NotFoundServiceException(message="flow_version_not_found")

            stmt_flow = select(FlowModel).where(
                FlowModel.flow_id == flow_version_instance.flow_id
            )
            query_sql_flow = compile_query(stmt_flow)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_flow_binding",
                input={
                    "query": query_sql_flow,
                    "params": {"flow_id": str(flow_version_instance.flow_id)},
                },
                metadata={"retriever_name": "get_flow_binding"},
            ) as retriever_handle:
                flow = await session.execute(stmt_flow)
                flow_instance = flow.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow_instance else 0,
                            "found": flow_instance is not None,
                        }
                    )

            if flow_instance is None:
                raise NotFoundServiceException(message="flow_not_found")

            stmt_agent = select(AgentModel).where(
                AgentModel.agent_id == agent_version_instance.agent_id
            )
            query_sql_agent = compile_query(stmt_agent)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_binding",
                input={
                    "query": query_sql_agent,
                    "params": {"agent_id": str(agent_version_instance.agent_id)},
                },
                metadata={"retriever_name": "get_agent_binding"},
            ) as retriever_handle:
                agent = await session.execute(stmt_agent)
                agent_instance = agent.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if agent_instance else 0,
                            "found": agent_instance is not None,
                        }
                    )

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
                if self.cache_adapter:
                    key = f"agent_version_by_node:{node_id}"
                    await self.cache_adapter.set(
                        key,
                        {"agent_version_id": str(agent_version_id)},
                        ttl=AGENT_VERSION_BY_NODE_CACHE_TTL,
                    )
                return instance

    async def get_agent_version_id_by_node_id(self, node_id: UUID) -> UUID | None:
        key = f"agent_version_by_node:{node_id}"
        if cached := await self.cache_adapter.get(key):
            agent_version_id = cached.get("agent_version_id")
            return UUID(agent_version_id) if agent_version_id else None

        async with self.db.get_session() as session:
            stmt = select(NodeAgentBindingModel).where(
                NodeAgentBindingModel.node_id == node_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.get_agent_version_id_by_node_id",
                input={
                    "query": query_sql,
                    "params": {"node_id": str(node_id)},
                },
                metadata={"retriever_name": "get_agent_version_id_by_node_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                binding = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if binding else 0,
                            "found": binding is not None,
                        }
                    )

                agent_version_id = binding.agent_version_id if binding else None

                await self.cache_adapter.set(
                    key,
                    {
                        "agent_version_id": str(agent_version_id)
                        if agent_version_id
                        else None
                    },
                    ttl=AGENT_VERSION_BY_NODE_CACHE_TTL,
                )
                return agent_version_id

    # Todo: this code should staying here ?
    async def resolve_effective_rag_config_id_for_node(
        self, node_id: UUID
    ) -> UUID | None:
        async with self.db.get_session() as session:
            stmt = select(NodeModel.rag_config_id).where(NodeModel.node_id == node_id)
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.agents.agents_repository.resolve_effective_rag_config_id_for_node",
                input={
                    "query": query_sql,
                    "params": {"node_id": str(node_id)},
                },
                metadata={"retriever_name": "resolve_effective_rag_config_id_for_node"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                node_rid = result.scalar_one_or_none()
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if node_rid is not None else 0,
                            "found": node_rid is not None,
                        }
                    )
        if node_rid is not None:
            return node_rid
        agent_version_id = await self.get_agent_version_id_by_node_id(node_id)
        if agent_version_id is None:
            return None
        agent_version = await self.get_agent_version(agent_version_id)
        if agent_version is None:
            return None
        return agent_version.rag_config_id

    async def list_node_bindings_by_agent_version_id(
        self, *, tenant_id: UUID, agent_version_id: UUID
    ) -> list[NodeAgentBindingModel]:
        async with self.db.get_session() as session:
            stmt_av = (
                select(AgentVersionModel.agent_version_id)
                .join(AgentModel, AgentVersionModel.agent_id == AgentModel.agent_id)
                .where(
                    AgentVersionModel.agent_version_id == agent_version_id,
                    AgentModel.tenant_id == tenant_id,
                )
            )
            result_av = await session.execute(stmt_av)
            if result_av.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="agent_version_not_found")
            stmt = (
                select(NodeAgentBindingModel)
                .where(
                    NodeAgentBindingModel.agent_version_id == agent_version_id,
                )
                .order_by(NodeAgentBindingModel.node_agent_binding_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
