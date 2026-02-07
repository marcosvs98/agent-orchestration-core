from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodePromptUpdate
from domain.prompts.schemas.system_prompt_template import SystemPromptTemplate
from infra.database import DatabaseConnection
from infra.database.models.prompts.node_prompt import NodePrompt as NodePromptModel
from infra.database.models.prompts.system_prompt_template import (
    SystemPromptTemplate as SystemPromptTemplateModel,
)


class PromptRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_active_prompt(self, node_type: str) -> Optional[NodePrompt]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.prompts.prompt_repository.get_active_prompt",
            input={"node_type": node_type},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(NodePromptModel)
                    .where(
                        NodePromptModel.node_type == node_type,
                        NodePromptModel.is_active.is_(True),
                    )
                    .order_by(NodePromptModel.version.desc())
                )
                model = result.scalar_one_or_none()
                if model:
                    return NodePrompt.model_validate(model.to_dict())
                return None

    async def get_prompt_by_id(self, prompt_id: UUID) -> Optional[NodePrompt]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.prompts.prompt_repository.get_prompt_by_id",
            input={"prompt_id": str(prompt_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(NodePromptModel).where(
                        NodePromptModel.prompt_id == prompt_id
                    )
                )
                model = result.scalar_one_or_none()
                if model:
                    return NodePrompt.model_validate(model.to_dict())
                return None

    async def create_prompt(
        self, prompt: NodePromptCreate, frozen_hash: str
    ) -> NodePrompt:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_existing_active",
                input={"node_type": prompt.node_type},
            ):
                existing = await session.execute(
                    select(NodePromptModel).where(
                        NodePromptModel.node_type == prompt.node_type,
                        NodePromptModel.is_active.is_(True),
                    )
                )
                existing_prompt = existing.scalar_one_or_none()
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
                    input_schema_id=prompt.input_schema_id,
                    output_schema_id=prompt.output_schema_id,
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
            with self.tracer.observe(
                as_type="retriever",
                name="domain.prompts.prompt_repository.get_prompt_for_update",
                input={"prompt_id": str(prompt_id)},
            ):
                result = await session.execute(
                    select(NodePromptModel)
                    .where(NodePromptModel.prompt_id == prompt_id)
                    .with_for_update()
                )
                model = result.scalar_one_or_none()
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
                    input_schema_id=update_data.input_schema_id
                    if update_data.input_schema_id is not None
                    else old_model.input_schema_id,
                    output_schema_id=update_data.output_schema_id
                    if update_data.output_schema_id is not None
                    else old_model.output_schema_id,
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
        with self.tracer.observe(
            as_type="retriever",
            name="domain.prompts.prompt_repository.get_prompt_history",
            input={"node_type": node_type},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(NodePromptModel)
                    .where(NodePromptModel.node_type == node_type)
                    .order_by(NodePromptModel.version.desc())
                )
                models = result.scalars().all()
                return [NodePrompt.model_validate(model.to_dict()) for model in models]

    async def get_system_prompt_template(
        self, template_id: UUID
    ) -> Optional[SystemPromptTemplate]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.prompts.prompt_repository.get_system_prompt_template",
            input={"template_id": str(template_id)},
        ):
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(SystemPromptTemplateModel).where(
                        SystemPromptTemplateModel.template_id == template_id
                    )
                )
                model = result.scalar_one_or_none()
                if model:
                    return SystemPromptTemplate.model_validate(model.to_dict())
                return None
