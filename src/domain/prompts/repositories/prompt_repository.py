from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodePromptUpdate
from infra.database import DatabaseConnection
from infra.database.models.prompts.node_prompt import NodePrompt as NodePromptModel


class PromptRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_active_prompt(self, node_type: str) -> Optional[NodePrompt]:
        async with self.db.get_session() as session:
            stmt = (
                select(NodePromptModel)
                .where(
                    NodePromptModel.node_type == node_type,
                    NodePromptModel.is_active.is_(True),
                )
                .order_by(NodePromptModel.version.desc())
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_active_prompt",
                input={"query": query_sql, "params": {"node_type": node_type}},
                metadata={"retriever_name": "get_active_prompt"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if model else 0,
                            "found": model is not None,
                        }
                    )

                if model:
                    return NodePrompt.model_validate(model.to_dict())
                return None

    async def get_prompt_by_id(self, prompt_id: UUID) -> Optional[NodePrompt]:
        async with self.db.get_session() as session:
            stmt = select(NodePromptModel).where(NodePromptModel.prompt_id == prompt_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_prompt_by_id",
                input={
                    "query": query_sql,
                    "params": {"prompt_id": str(prompt_id)},
                },
                metadata={"retriever_name": "get_prompt_by_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if model else 0,
                            "found": model is not None,
                        }
                    )

                if model:
                    return NodePrompt.model_validate(model.to_dict())
                return None

    async def create_prompt(
        self, prompt: NodePromptCreate, frozen_hash: str
    ) -> NodePrompt:
        async with self.db.get_session() as session:
            stmt = select(NodePromptModel).where(
                NodePromptModel.node_type == prompt.node_type,
                NodePromptModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_existing_active",
                input={
                    "query": query_sql,
                    "params": {"node_type": prompt.node_type},
                },
                metadata={"retriever_name": "get_existing_active"},
            ) as retriever_handle:
                existing = await session.execute(stmt)
                existing_prompt = existing.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if existing_prompt else 0,
                            "found": existing_prompt is not None,
                        }
                    )

            next_version = 1
            if existing_prompt:
                next_version = existing_prompt.version + 1
                existing_prompt.is_active = False
                session.add(existing_prompt)

            with self.tracer.observe(
                as_type="tool",
                name="domain.prompts.prompt_repository.create_prompt",
                input={"node_type": prompt.node_type},
            ):
                model = NodePromptModel(
                    node_type=prompt.node_type,
                    template_text=prompt.template_text,
                    output_schema=prompt.output_schema,
                    version=next_version,
                    frozen_hash=frozen_hash,
                    is_active=True,
                    description=prompt.description,
                    created_by=prompt.created_by,
                )
                session.add(model)
                await session.commit()
                await session.refresh(model)
                return NodePrompt.model_validate(model.to_dict())

    async def update_prompt(
        self, prompt_id: UUID, update_data: NodePromptUpdate, frozen_hash: str
    ) -> NodePrompt:
        async with self.db.get_session() as session:
            stmt = (
                select(NodePromptModel)
                .where(NodePromptModel.prompt_id == prompt_id)
                .with_for_update()
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_prompt_for_update",
                input={
                    "query": query_sql,
                    "params": {"prompt_id": str(prompt_id)},
                },
                metadata={"retriever_name": "get_prompt_for_update"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if model else 0,
                            "found": model is not None,
                        }
                    )

            if not model:
                raise ValueError(f"Prompt with id {prompt_id} not found")

            old_model = model
            old_model.is_active = False

            with self.tracer.observe(
                as_type="tool",
                name="domain.prompts.prompt_repository.update_prompt",
                input={"prompt_id": str(prompt_id)},
            ):
                new_version = old_model.version + 1
                new_model = NodePromptModel(
                    node_type=old_model.node_type,
                    template_text=update_data.template_text or old_model.template_text,
                    output_schema=update_data.output_schema
                    if update_data.output_schema is not None
                    else old_model.output_schema,
                    version=new_version,
                    frozen_hash=frozen_hash,
                    is_active=True,
                    description=update_data.description
                    if update_data.description is not None
                    else old_model.description,
                    created_by=old_model.created_by,
                )
                session.add(old_model)
                session.add(new_model)
                await session.commit()
                await session.refresh(new_model)
                return NodePrompt.model_validate(new_model.to_dict())

    async def deactivate_prompt(self, prompt_id: UUID) -> None:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.prompts.prompt_repository.deactivate_prompt",
                input={"prompt_id": str(prompt_id)},
            ):
                await session.execute(
                    update(NodePromptModel)
                    .where(NodePromptModel.prompt_id == prompt_id)
                    .values(is_active=False)
                )
                await session.commit()

    async def get_prompt_history(self, node_type: str) -> list[NodePrompt]:
        async with self.db.get_session() as session:
            stmt = (
                select(NodePromptModel)
                .where(NodePromptModel.node_type == node_type)
                .order_by(NodePromptModel.version.desc())
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_prompt_history",
                input={
                    "query": query_sql,
                    "params": {"node_type": node_type},
                },
                metadata={"retriever_name": "get_prompt_history"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                models = result.scalars().all()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(models),
                            "found": len(models) > 0,
                        }
                    )

                return [NodePrompt.model_validate(model.to_dict()) for model in models]
