from uuid import UUID
import contextlib

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.ai_policy.ai_task import AITask as AITaskModel
from infra.database.models.ai_policy.execution_policy import (
    AIExecutionPolicy as AIExecutionPolicyModel,
)
from infra.database.models.ai_policy.execution_policy_version import (
    AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
)
from infra.database.models.ai_policy.model import Model as ModelModel
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from utils.query_compiler import compile_query


class AIRepository:
    def __init__(
        self, database_connection: DatabaseConnection, tracer: RuntimeTracerPort
    ) -> None:
        self.db = database_connection
        self.tracer = tracer

    async def get_ai_task(self, ai_task_id: UUID) -> AITaskModel | None:
        async with self.db.get_session() as session:
            stmt = select(AITaskModel).where(AITaskModel.ai_task_id == ai_task_id)
            query_sql = compile_query(stmt)

            span_cm = (
                self.tracer.observe(
                    as_type="retriever",
                    name="domain.ai_policy.repository.get_ai_task",
                    input={
                        "query": query_sql,
                        "params": {"ai_task_id": str(ai_task_id)},
                    },
                    metadata={"retriever_name": "get_ai_task"},
                )
                if self.tracer
                else contextlib.nullcontext()
            )
            with span_cm as retriever_handle:
                result = await session.execute(stmt)
                ai_task = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if ai_task else 0,
                            "found": ai_task is not None,
                        }
                    )

                return ai_task

    async def list_ai_tasks(self) -> list[AITaskModel]:
        async with self.db.get_session() as session:
            stmt = select(AITaskModel).order_by(AITaskModel.name.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_model(self, model_id: UUID) -> ModelModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ModelModel).where(ModelModel.model_id == model_id)
            )
            return result.scalar_one_or_none()

    async def list_models(self) -> list[ModelModel]:
        async with self.db.get_session() as session:
            stmt = select(ModelModel).order_by(ModelModel.name.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_ai_execution_policy(
        self, ai_execution_policy_id: UUID
    ) -> AIExecutionPolicyModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AIExecutionPolicyModel).where(
                    AIExecutionPolicyModel.ai_execution_policy_id
                    == ai_execution_policy_id
                )
            )
            return result.scalar_one_or_none()

    async def list_ai_execution_policies(
        self, *, tenant_id: UUID, limit: int
    ) -> list[AIExecutionPolicyModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AIExecutionPolicyModel)
                .where(AIExecutionPolicyModel.tenant_id == tenant_id)
                .order_by(AIExecutionPolicyModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_ai_execution_policy(
        self, *, tenant_id: UUID, description: str | None, created_by: str
    ) -> AIExecutionPolicyModel:
        async with self.db.get_session() as session:
            instance = AIExecutionPolicyModel(
                tenant_id=tenant_id, description=description
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_ai_execution_policy_version(
        self, ai_execution_policy_version_id: UUID
    ) -> AIExecutionPolicyVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AIExecutionPolicyVersionModel).where(
                    AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                    == ai_execution_policy_version_id
                )
            )
            return result.scalar_one_or_none()

    async def list_ai_execution_policy_versions(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: UUID | None = None,
        status_filter: list[str] | None = None,
        limit: int,
    ) -> list[AIExecutionPolicyVersionModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AIExecutionPolicyVersionModel)
                .join(
                    AIExecutionPolicyModel,
                    AIExecutionPolicyVersionModel.ai_execution_policy_id
                    == AIExecutionPolicyModel.ai_execution_policy_id,
                )
                .where(AIExecutionPolicyModel.tenant_id == tenant_id)
            )
            if ai_execution_policy_id is not None:
                stmt = stmt.where(
                    AIExecutionPolicyVersionModel.ai_execution_policy_id
                    == ai_execution_policy_id
                )
            if status_filter is not None:
                stmt = stmt.where(
                    AIExecutionPolicyVersionModel.status.in_(status_filter)
                )
            stmt = stmt.order_by(
                AIExecutionPolicyVersionModel.version_major.desc(),
                AIExecutionPolicyVersionModel.version_minor.desc(),
                AIExecutionPolicyVersionModel.version_patch.desc(),
            ).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_ai_execution_policy_version(
        self,
        *,
        ai_execution_policy_id: UUID,
        source_version_id: UUID | None = None,
        model_id: UUID,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        config_hash: str | None = None,
        created_by: str,
    ) -> AIExecutionPolicyVersionModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                source_version = await session.execute(
                    select(AIExecutionPolicyVersionModel).where(
                        AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                        == source_version_id
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
                if config_hash is None:
                    config_hash = source.config_hash
            else:
                if (
                    version_major is None
                    or version_minor is None
                    or version_patch is None
                ):
                    last_version = await session.execute(
                        select(AIExecutionPolicyVersionModel)
                        .where(
                            AIExecutionPolicyVersionModel.ai_execution_policy_id
                            == ai_execution_policy_id
                        )
                        .order_by(
                            AIExecutionPolicyVersionModel.version_major.desc(),
                            AIExecutionPolicyVersionModel.version_minor.desc(),
                            AIExecutionPolicyVersionModel.version_patch.desc(),
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

            instance = AIExecutionPolicyVersionModel(
                ai_execution_policy_id=ai_execution_policy_id,
                model_id=model_id,
                status="DRAFT",
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                config_hash=config_hash,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def set_ai_execution_policy_version_status(
        self, *, ai_execution_policy_version_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AIExecutionPolicyVersionModel).where(
                    AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                    == ai_execution_policy_version_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(
                    message="ai_execution_policy_version_not_found"
                )
            instance.status = str(status)
            await session.commit()
