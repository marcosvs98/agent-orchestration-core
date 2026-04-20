from uuid import UUID

from sqlalchemy import func, select

from adapters.cache.redis_adapter import RedisAdapter
from domain.common.schemas.versioning import VersionStatus
from utils.query_compiler import compile_query
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
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
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter

    async def get_tool(self, tool_id: UUID) -> ToolModel | None:
        async with self.db.get_session() as session:
            stmt = select(ToolModel).where(ToolModel.tool_id == tool_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_tool",
                input={"query": query_sql, "params": {"tool_id": str(tool_id)}},
                metadata={"retriever_name": "get_tool"},
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

                return instance

    async def get_tool_by_name(self, name: str) -> ToolModel | None:
        async with self.db.get_session() as session:
            stmt = select(ToolModel).where(ToolModel.name == name)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_tool_by_name",
                input={"query": query_sql, "params": {"name": name}},
                metadata={"retriever_name": "get_tool_by_name"},
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

                return instance

    async def create_tool(self, *, name: str | None, created_by: str) -> ToolModel:
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_repository.create_tool",
            input={"name": name},
        ):
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
                    ToolConfigModel,
                    ToolModel.tool_id == ToolConfigModel.tool_id,
                )
                .where(ToolConfigModel.tenant_id == tenant_id)
            )
            if status_filter:
                stmt = stmt.where(ToolConfigModel.status.in_(status_filter))
            stmt = stmt.distinct().order_by(ToolModel.created_at.desc()).limit(limit)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.list_tools",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_tools"},
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

    async def list_tool_capabilities_preview(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[tuple[UUID, str | None, UUID, str]]:
        async with self.db.get_session() as session:
            stmt = (
                select(
                    ToolModel.tool_id,
                    ToolModel.name,
                    ToolConfigModel.tool_config_id,
                    ToolConfigModel.status,
                )
                .join(
                    ToolConfigModel,
                    ToolModel.tool_id == ToolConfigModel.tool_id,
                )
                .where(
                    ToolConfigModel.tenant_id == tenant_id,
                    ToolConfigModel.status == VersionStatus.PUBLISHED.value,
                )
                .order_by(ToolModel.name.asc().nulls_last())
                .limit(limit)
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.list_tool_capabilities_preview",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_tool_capabilities_preview"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                rows = list(result.all())
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(rows),
                            "found": len(rows) > 0,
                        }
                    )
                return [(tid, name, tcid, str(st)) for tid, name, tcid, st in rows]

    async def get_max_version_patch(
        self,
        *,
        tool_id: UUID,
        tenant_id: UUID,
        version_major: int = 1,
        version_minor: int = 0,
    ) -> int:
        async with self.db.get_session() as session:
            stmt = select(
                func.coalesce(func.max(ToolConfigModel.version_patch), -1).label("max_patch")
            ).where(
                ToolConfigModel.tool_id == tool_id,
                ToolConfigModel.tenant_id == tenant_id,
                ToolConfigModel.version_major == version_major,
                ToolConfigModel.version_minor == version_minor,
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_max_version_patch",
                input={
                    "query": query_sql,
                    "params": {"tool_id": str(tool_id), "tenant_id": str(tenant_id)},
                },
                metadata={"retriever_name": "get_max_version_patch"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                row = result.one()
                if retriever_handle:
                    retriever_handle.success(output={"max_patch": row.max_patch})
                return int(row.max_patch)

    async def get_tool_config(self, tool_config_id: UUID) -> ToolConfigModel | None:
        async with self.db.get_session() as session:
            stmt = select(ToolConfigModel).where(ToolConfigModel.tool_config_id == tool_config_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_tool_config",
                input={
                    "query": query_sql,
                    "params": {"tool_config_id": str(tool_config_id)},
                },
                metadata={"retriever_name": "get_tool_config"},
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

                return instance

    @staticmethod
    def _published_batch_cache_key(tenant_id: UUID, tool_config_ids: list[UUID]) -> str:
        sorted_ids = "|".join(sorted(str(x) for x in tool_config_ids))
        return f"tools:pub_cfg_batch:{tenant_id}:{sorted_ids}"

    @staticmethod
    def _rows_to_cache_payload(
        rows: list[tuple[ToolConfigModel, ToolModel]],
    ) -> dict:
        return {
            "rows": [
                {
                    "tool_config": cfg.to_dict(),
                    "tool": tool.to_dict(),
                }
                for cfg, tool in rows
            ]
        }

    @staticmethod
    def _rows_from_cache_payload(
        payload: dict,
    ) -> list[tuple[ToolConfigModel, ToolModel]]:
        out: list[tuple[ToolConfigModel, ToolModel]] = []
        raw_rows = payload.get("rows")
        if not isinstance(raw_rows, list):
            return out
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            cfg_raw = item.get("tool_config")
            tool_raw = item.get("tool")
            if not isinstance(cfg_raw, dict) or not isinstance(tool_raw, dict):
                continue
            out.append(
                (
                    ToolConfigModel.from_dict(cfg_raw),
                    ToolModel.from_dict(tool_raw),
                )
            )
        return out

    async def list_published_tool_configs_with_tools_by_config_ids(
        self,
        *,
        tenant_id: UUID,
        tool_config_ids: list[UUID],
    ) -> list[tuple[ToolConfigModel, ToolModel]]:
        if not tool_config_ids:
            return []
        cache_key = self._published_batch_cache_key(tenant_id, tool_config_ids)
        if self.cache_adapter:
            cached = await self.cache_adapter.get(cache_key)
            if isinstance(cached, dict) and "rows" in cached:
                return self._rows_from_cache_payload(cached)
        async with self.db.get_session() as session:
            stmt = (
                select(ToolConfigModel, ToolModel)
                .join(ToolModel, ToolModel.tool_id == ToolConfigModel.tool_id)
                .where(
                    ToolConfigModel.tenant_id == tenant_id,
                    ToolConfigModel.tool_config_id.in_(tool_config_ids),
                    ToolConfigModel.status == VersionStatus.PUBLISHED.value,
                )
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.list_published_tool_configs_with_tools_by_config_ids",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "tool_config_ids": [str(x) for x in tool_config_ids],
                    },
                },
                metadata={"retriever_name": "list_published_tool_configs_with_tools_by_config_ids"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                rows = list(result.all())
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(rows),
                            "found": len(rows) > 0,
                        }
                    )
                if self.cache_adapter:
                    await self.cache_adapter.set(
                        cache_key,
                        self._rows_to_cache_payload(rows),
                        ttl=90,
                    )
                return rows

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
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.list_tool_configs",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_tool_configs"},
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
                stmt = select(ToolConfigModel).where(
                    ToolConfigModel.tool_config_id == source_config_id
                )
                query_sql = compile_query(stmt)

                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.tools.tools_repository.get_source_config",
                    input={
                        "query": query_sql,
                        "params": {"source_config_id": str(source_config_id)},
                    },
                    metadata={"retriever_name": "get_source_config"},
                ) as retriever_handle:
                    source_config = await session.execute(stmt)
                    source = source_config.scalar_one_or_none()

                    if retriever_handle:
                        retriever_handle.success(
                            output={
                                "result_count": 1 if source else 0,
                                "found": source is not None,
                            }
                        )

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
                stmt = (
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
                query_sql = compile_query(stmt)

                with self.tracer.observe(
                    as_type="retriever",
                    name="domain.tools.tools_repository.get_latest_config",
                    input={
                        "query": query_sql,
                        "params": {
                            "tool_id": str(tool_id),
                            "tenant_id": str(tenant_id),
                        },
                    },
                    metadata={"retriever_name": "get_latest_config"},
                ) as retriever_handle:
                    last_config = await session.execute(stmt)
                    last = last_config.scalar_one_or_none()

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
                name="domain.tools.tools_repository.create_tool_config",
                input={"tool_id": str(tool_id), "tenant_id": str(tenant_id)},
            ):
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

    async def set_tool_config_status(self, *, tool_config_id: UUID, status: VersionStatus) -> None:
        async with self.db.get_session() as session:
            stmt = select(ToolConfigModel).where(ToolConfigModel.tool_config_id == tool_config_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_tool_config_status",
                input={
                    "query": query_sql,
                    "params": {"tool_config_id": str(tool_config_id)},
                },
                metadata={"retriever_name": "get_tool_config_status"},
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
                raise NotFoundServiceException(message="tool_config_not_found")
            instance.status = str(status)
            with self.tracer.observe(
                as_type="tool",
                name="domain.tools.tools_repository.set_tool_config_status",
                input={"tool_config_id": str(tool_config_id), "status": str(status)},
            ):
                await session.commit()

    async def create_agent_version_tool_binding(
        self,
        *,
        agent_version_id: UUID,
        tool_config_id: UUID,
        created_by: str,
    ) -> AgentVersionToolBindingModel:
        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_agent_version_binding",
                input={
                    "query": query_sql,
                    "params": {"agent_version_id": str(agent_version_id)},
                },
                metadata={"retriever_name": "get_agent_version_binding"},
            ) as retriever_handle:
                agent_version = await session.execute(stmt)
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

            stmt = select(AgentModel).where(AgentModel.agent_id == agent_version_instance.agent_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_agent_binding",
                input={
                    "query": query_sql,
                    "params": {"agent_id": str(agent_version_instance.agent_id)},
                },
                metadata={"retriever_name": "get_agent_binding"},
            ) as retriever_handle:
                agent = await session.execute(stmt)
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

            stmt = select(ToolConfigModel).where(ToolConfigModel.tool_config_id == tool_config_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.tools.tools_repository.get_tool_config_binding",
                input={
                    "query": query_sql,
                    "params": {"tool_config_id": str(tool_config_id)},
                },
                metadata={"retriever_name": "get_tool_config_binding"},
            ) as retriever_handle:
                tool_config = await session.execute(stmt)
                tool_config_instance = tool_config.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if tool_config_instance else 0,
                            "found": tool_config_instance is not None,
                        }
                    )

            if tool_config_instance is None:
                raise NotFoundServiceException(message="tool_config_not_found")

            if agent_instance.tenant_id != tool_config_instance.tenant_id:
                raise DomainValidationException(
                    message="agent_version_and_tool_config_must_belong_to_same_tenant"
                )

            with self.tracer.observe(
                as_type="tool",
                name="domain.tools.tools_repository.create_agent_version_tool_binding",
                input={
                    "agent_version_id": str(agent_version_id),
                    "tool_config_id": str(tool_config_id),
                },
            ):
                instance = AgentVersionToolBindingModel(
                    agent_version_id=agent_version_id,
                    tool_config_id=tool_config_id,
                )
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def list_tool_bindings_by_agent_version_id(
        self, *, tenant_id: UUID, agent_version_id: UUID
    ) -> list[AgentVersionToolBindingModel]:
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
                select(AgentVersionToolBindingModel)
                .where(
                    AgentVersionToolBindingModel.agent_version_id == agent_version_id,
                )
                .order_by(AgentVersionToolBindingModel.agent_version_tool_binding_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
