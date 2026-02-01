from uuid import UUID

from sqlalchemy import select

from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.onboarding.onboarding import Onboarding as OnboardingModel
from infra.database.models.onboarding.onboarding_run import (
    OnboardingRun as OnboardingRunModel,
)
from infra.database.models.onboarding.onboarding_step import (
    OnboardingStep as OnboardingStepModel,
)
from infra.database.models.onboarding.onboarding_version import (
    OnboardingVersion as OnboardingVersionModel,
)
from infra.database.models.onboarding.step_run import StepRun as StepRunModel


class OnboardingRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_onboarding(self, onboarding_id: UUID) -> OnboardingModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(OnboardingModel).where(
                    OnboardingModel.onboarding_id == onboarding_id
                )
            )
            return result.scalar_one_or_none()

    async def list_onboardings(
        self, *, tenant_id: UUID, limit: int
    ) -> list[OnboardingModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(OnboardingModel)
                .where(OnboardingModel.tenant_id == tenant_id)
                .order_by(OnboardingModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_onboarding(
        self, *, tenant_id: UUID, name: str | None, created_by: str
    ) -> OnboardingModel:
        async with self.db.get_session() as session:
            instance = OnboardingModel(
                tenant_id=tenant_id, name=name, created_by=created_by
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_onboarding_version(
        self, onboarding_version_id: UUID
    ) -> OnboardingVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(OnboardingVersionModel).where(
                    OnboardingVersionModel.onboarding_version_id
                    == onboarding_version_id
                )
            )
            return result.scalar_one_or_none()

    async def list_onboarding_versions(
        self, onboarding_id: UUID
    ) -> list[OnboardingVersionModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(OnboardingVersionModel)
                .where(OnboardingVersionModel.onboarding_id == onboarding_id)
                .order_by(
                    OnboardingVersionModel.version_major.desc(),
                    OnboardingVersionModel.version_minor.desc(),
                    OnboardingVersionModel.version_patch.desc(),
                )
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_onboarding_version(
        self,
        *,
        onboarding_id: UUID,
        source_version_id: UUID | None = None,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        created_by: str,
    ) -> OnboardingVersionModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                source_version = await session.execute(
                    select(OnboardingVersionModel).where(
                        OnboardingVersionModel.onboarding_version_id
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
            else:
                if (
                    version_major is None
                    or version_minor is None
                    or version_patch is None
                ):
                    last_version = await session.execute(
                        select(OnboardingVersionModel)
                        .where(OnboardingVersionModel.onboarding_id == onboarding_id)
                        .order_by(
                            OnboardingVersionModel.version_major.desc(),
                            OnboardingVersionModel.version_minor.desc(),
                            OnboardingVersionModel.version_patch.desc(),
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

            instance = OnboardingVersionModel(
                onboarding_id=onboarding_id,
                status="DRAFT",
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_onboarding_run(
        self, onboarding_run_id: UUID
    ) -> OnboardingRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(OnboardingRunModel).where(
                    OnboardingRunModel.onboarding_run_id == onboarding_run_id
                )
            )
            return result.scalar_one_or_none()

    async def create_onboarding_run(
        self, *, onboarding_version_id: UUID, created_by: str
    ) -> OnboardingRunModel:
        async with self.db.get_session() as session:
            version = await session.execute(
                select(OnboardingVersionModel).where(
                    OnboardingVersionModel.onboarding_version_id
                    == onboarding_version_id
                )
            )
            if version.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="onboarding_version_not_found")
            instance = OnboardingRunModel(onboarding_version_id=onboarding_version_id)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_onboarding_step(
        self, onboarding_step_id: UUID
    ) -> OnboardingStepModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(OnboardingStepModel).where(
                    OnboardingStepModel.onboarding_step_id == onboarding_step_id
                )
            )
            return result.scalar_one_or_none()

    async def list_onboarding_steps(
        self, onboarding_version_id: UUID
    ) -> list[OnboardingStepModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(OnboardingStepModel)
                .where(
                    OnboardingStepModel.onboarding_version_id == onboarding_version_id
                )
                .order_by(OnboardingStepModel.created_at.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_step(self, step_run_id: UUID) -> StepRunModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(StepRunModel).where(StepRunModel.step_run_id == step_run_id)
            )
            return result.scalar_one_or_none()

    async def list_steps(self, onboarding_run_id: UUID) -> list[StepRunModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(StepRunModel)
                .where(StepRunModel.onboarding_run_id == onboarding_run_id)
                .order_by(StepRunModel.created_at.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_step(
        self,
        *,
        onboarding_run_id: UUID,
        onboarding_step_id: UUID,
        name: str,
        schema_id: UUID | None = None,
    ) -> StepRunModel:
        async with self.db.get_session() as session:
            run = await session.execute(
                select(OnboardingRunModel).where(
                    OnboardingRunModel.onboarding_run_id == onboarding_run_id
                )
            )
            if run.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="onboarding_run_not_found")
            step = await session.execute(
                select(OnboardingStepModel).where(
                    OnboardingStepModel.onboarding_step_id == onboarding_step_id
                )
            )
            if step.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="onboarding_step_not_found")
            instance = StepRunModel(
                onboarding_run_id=onboarding_run_id,
                onboarding_step_id=onboarding_step_id,
                name=name,
                status="PENDING",
                schema_id=schema_id,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def update_step_status(
        self,
        *,
        step_run_id: UUID,
        status: str,
        input_payload: dict[str, object] | None = None,
        output_payload: dict[str, object] | None = None,
    ) -> StepRunModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(StepRunModel).where(StepRunModel.step_run_id == step_run_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="step_run_not_found")
            instance.status = status
            if input_payload is not None:
                instance.input_payload = input_payload
            if output_payload is not None:
                instance.output_payload = output_payload
            await session.commit()
            await session.refresh(instance)
            return instance
