from uuid import UUID

from sqlalchemy import select

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from infra.database import DatabaseConnection
from infra.database.models.prompts.user_prompt import UserPrompt as UserPromptModel
from utils.query_compiler import compile_query


class UserPromptsRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def list_active(self, tenant_id: UUID, limit: int = 200) -> list[UserPromptModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(UserPromptModel)
                .where(
                    UserPromptModel.tenant_id == tenant_id,
                    UserPromptModel.is_active.is_(True),
                )
                .order_by(UserPromptModel.created_at.desc())
                .limit(limit)
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.user_prompts.user_prompts_repository.list_active",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id), "limit": limit},
                },
                metadata={"retriever_name": "list_active"},
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

    async def get_by_id(
        self, tenant_id: UUID, user_prompt_id: UUID
    ) -> UserPromptModel | None:
        async with self.db.get_session() as session:
            stmt = select(UserPromptModel).where(
                UserPromptModel.tenant_id == tenant_id,
                UserPromptModel.user_prompt_id == user_prompt_id,
                UserPromptModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.user_prompts.user_prompts_repository.get_by_id",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "user_prompt_id": str(user_prompt_id),
                    },
                },
                metadata={"retriever_name": "get_by_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                item = result.scalar_one_or_none()
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if item else 0,
                            "found": item is not None,
                        }
                    )
                return item

    async def create(
        self, tenant_id: UUID, title: str, content: str, created_by: str
    ) -> UserPromptModel:
        async with self.db.get_session() as session:
            stmt_latest = (
                select(UserPromptModel)
                .where(
                    UserPromptModel.tenant_id == tenant_id,
                    UserPromptModel.title == title,
                )
                .order_by(UserPromptModel.version.desc())
                .limit(1)
            )
            query_sql_latest = compile_query(stmt_latest)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.user_prompts.user_prompts_repository.get_latest_by_title",
                input={
                    "query": query_sql_latest,
                    "params": {"tenant_id": str(tenant_id), "title": title},
                },
                metadata={"retriever_name": "get_latest_by_title"},
            ) as retriever_handle:
                latest_result = await session.execute(stmt_latest)
                latest = latest_result.scalar_one_or_none()
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if latest else 0,
                            "found": latest is not None,
                        }
                    )

            next_version = 1 if latest is None else latest.version + 1

            stmt_active = select(UserPromptModel).where(
                UserPromptModel.tenant_id == tenant_id,
                UserPromptModel.title == title,
                UserPromptModel.is_active.is_(True),
            )
            query_sql_active = compile_query(stmt_active)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.user_prompts.user_prompts_repository.get_active_by_title",
                input={
                    "query": query_sql_active,
                    "params": {"tenant_id": str(tenant_id), "title": title},
                },
                metadata={"retriever_name": "get_active_by_title"},
            ) as retriever_handle:
                active_result = await session.execute(stmt_active)
                active_items = list(active_result.scalars().all())
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(active_items),
                            "found": len(active_items) > 0,
                        }
                    )

            for item in active_items:
                item.is_active = False

            with self.tracer.observe(
                as_type="tool",
                name="domain.user_prompts.user_prompts_repository.create",
                input={
                    "tenant_id": str(tenant_id),
                    "title": title,
                    "version": next_version,
                },
            ):
                instance = UserPromptModel(
                    tenant_id=tenant_id,
                    title=title,
                    content=content,
                    version=next_version,
                    is_active=True,
                    created_by=created_by,
                )
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance

    async def deactivate(self, tenant_id: UUID, user_prompt_id: UUID) -> bool:
        async with self.db.get_session() as session:
            stmt = select(UserPromptModel).where(
                UserPromptModel.tenant_id == tenant_id,
                UserPromptModel.user_prompt_id == user_prompt_id,
                UserPromptModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)
            with self.tracer.observe(
                as_type="retriever",
                name="domain.user_prompts.user_prompts_repository.get_for_deactivate",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "user_prompt_id": str(user_prompt_id),
                    },
                },
                metadata={"retriever_name": "get_for_deactivate"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                item = result.scalar_one_or_none()
                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if item else 0,
                            "found": item is not None,
                        }
                    )

            if item is None:
                return False

            with self.tracer.observe(
                as_type="tool",
                name="domain.user_prompts.user_prompts_repository.deactivate",
                input={
                    "tenant_id": str(tenant_id),
                    "user_prompt_id": str(user_prompt_id),
                },
            ):
                item.is_active = False
                await session.commit()
                return True
