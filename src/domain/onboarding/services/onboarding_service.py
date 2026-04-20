from uuid import UUID

from domain.onboarding.ports.service import OnboardingServicePort
from domain.onboarding.repositories.onboarding_repository import OnboardingRepository
from domain.onboarding.schemas.onboarding import (
    Onboarding,
    OnboardingCreate,
    OnboardingRun,
    OnboardingRunCreate,
    OnboardingVersion,
    StepRun,
)
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)


class OnboardingService(OnboardingServicePort):
    def __init__(
        self,
        repository: OnboardingRepository,
        authoring_events: AuthoringEventRepository,
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def list_onboardings(self, *, tenant_id: UUID, limit: int = 200) -> list[Onboarding]:
        onboardings = await self.repository.list_onboardings(tenant_id=tenant_id, limit=limit)
        return [
            Onboarding(
                id=onboarding.onboarding_id,
                name=onboarding.name,
                created_by=onboarding.created_by,
            )
            for onboarding in onboardings
        ]

    async def create_onboarding(
        self, *, tenant_id: UUID, onboarding_create: OnboardingCreate, principal_id: str
    ) -> Onboarding:
        model = await self.repository.create_onboarding(
            tenant_id=tenant_id,
            name=onboarding_create.name,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="onboarding",
            resource_id=model.onboarding_id,
            version_id=None,
            event_type="ONBOARDING_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create onboarding",
            schema_version=1,
        )
        return Onboarding(id=model.onboarding_id, name=model.name, created_by=model.created_by)

    async def list_onboarding_versions(
        self, *, tenant_id: UUID, onboarding_id: str
    ) -> list[OnboardingVersion]:
        onboarding_uuid = UUID(onboarding_id)
        onboarding = await self.repository.get_onboarding(onboarding_uuid)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        versions = await self.repository.list_onboarding_versions(onboarding_uuid)
        return [
            OnboardingVersion(
                id=version.onboarding_version_id,
                onboarding_id=version.onboarding_id,
                status=version.status,
                version_major=version.version_major,
                version_minor=version.version_minor,
                version_patch=version.version_patch,
            )
            for version in versions
        ]

    async def create_onboarding_run(
        self,
        *,
        tenant_id: UUID,
        onboarding_run_create: OnboardingRunCreate,
        principal_id: str,
    ) -> OnboardingRun:
        version = await self.repository.get_onboarding_version(
            onboarding_run_create.onboarding_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        model = await self.repository.create_onboarding_run(
            onboarding_version_id=onboarding_run_create.onboarding_version_id,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="onboarding_run",
            resource_id=model.onboarding_run_id,
            version_id=None,
            event_type="ONBOARDING_RUN_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create onboarding run",
            schema_version=1,
        )
        return OnboardingRun(
            id=model.onboarding_run_id,
            onboarding_version_id=model.onboarding_version_id,
        )

    async def get_onboarding_run(self, *, tenant_id: UUID, onboarding_run_id: str) -> OnboardingRun:
        run_uuid = UUID(onboarding_run_id)
        run = await self.repository.get_onboarding_run(run_uuid)
        if run is None:
            raise NotFoundServiceException(message="onboarding_run_not_found")
        version = await self.repository.get_onboarding_version(run.onboarding_version_id)
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        return OnboardingRun(
            id=run.onboarding_run_id,
            onboarding_version_id=run.onboarding_version_id,
        )

    async def list_steps(self, *, tenant_id: UUID, onboarding_run_id: str) -> list[StepRun]:
        run_uuid = UUID(onboarding_run_id)
        run = await self.repository.get_onboarding_run(run_uuid)
        if run is None:
            raise NotFoundServiceException(message="onboarding_run_not_found")
        version = await self.repository.get_onboarding_version(run.onboarding_version_id)
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        steps = await self.repository.list_steps(run_uuid)
        return [
            StepRun(
                id=step.step_run_id,
                onboarding_run_id=step.onboarding_run_id,
                onboarding_step_id=step.onboarding_step_id,
                name=step.name,
                status=step.status,
                input_payload=step.input_payload,
                output_payload=step.output_payload,
                schema_id=step.schema_id,
            )
            for step in steps
        ]

    async def get_current_step(self, *, tenant_id: UUID, onboarding_run_id: str) -> StepRun | None:
        run_uuid = UUID(onboarding_run_id)
        run = await self.repository.get_onboarding_run(run_uuid)
        if run is None:
            raise NotFoundServiceException(message="onboarding_run_not_found")
        version = await self.repository.get_onboarding_version(run.onboarding_version_id)
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        steps = await self.repository.list_steps(run_uuid)
        for step in steps:
            if step.status in ("PENDING", "IN_PROGRESS"):
                return StepRun(
                    id=step.step_run_id,
                    onboarding_run_id=step.onboarding_run_id,
                    onboarding_step_id=step.onboarding_step_id,
                    name=step.name,
                    status=step.status,
                    input_payload=step.input_payload,
                    output_payload=step.output_payload,
                    schema_id=step.schema_id,
                )
        return None

    async def is_run_completed(self, *, tenant_id: UUID, onboarding_run_id: str) -> bool:
        run_uuid = UUID(onboarding_run_id)
        run = await self.repository.get_onboarding_run(run_uuid)
        if run is None:
            raise NotFoundServiceException(message="onboarding_run_not_found")
        version = await self.repository.get_onboarding_version(run.onboarding_version_id)
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        steps = await self.repository.list_steps(run_uuid)
        if not steps:
            return False
        return all(step.status in ("COMPLETED", "FAILED") for step in steps)

    async def advance_step(
        self,
        *,
        tenant_id: UUID,
        onboarding_run_id: str,
        step_run_id: str,
        input_payload: dict[str, object],
        principal_id: str,
    ) -> StepRun:
        run_uuid = UUID(onboarding_run_id)
        step_uuid = UUID(step_run_id)
        run = await self.repository.get_onboarding_run(run_uuid)
        if run is None:
            raise NotFoundServiceException(message="onboarding_run_not_found")
        version = await self.repository.get_onboarding_version(run.onboarding_version_id)
        if version is None:
            raise NotFoundServiceException(message="onboarding_version_not_found")
        onboarding = await self.repository.get_onboarding(version.onboarding_id)
        if onboarding is None or onboarding.tenant_id != tenant_id:
            raise NotFoundServiceException(message="onboarding_not_found")
        step_run = await self.repository.get_step(step_uuid)
        if step_run is None or step_run.onboarding_run_id != run_uuid:
            raise NotFoundServiceException(message="step_run_not_found")
        if step_run.status not in ("PENDING", "IN_PROGRESS"):
            raise DomainValidationException(message="step_run_not_in_valid_status_for_advance")
        was_pending = step_run.status == "PENDING"
        if was_pending:
            updated_step = await self.repository.update_step_status(
                step_run_id=step_uuid,
                status="IN_PROGRESS",
                input_payload=input_payload,
            )
            await self.authoring_events.append_event(
                tenant_id=tenant_id,
                resource_type="onboarding_step_run",
                resource_id=step_uuid,
                version_id=None,
                event_type="ONBOARDING_STEP_STARTED",
                change_type="UPDATE",
                principal_id=principal_id,
                justification="advance step",
                schema_version=1,
            )
        else:
            updated_step = await self.repository.update_step_status(
                step_run_id=step_uuid,
                status="IN_PROGRESS",
                input_payload=input_payload,
            )
        output_payload_result = {"result": "processed", "input": input_payload}
        updated_step = await self.repository.update_step_status(
            step_run_id=step_uuid,
            status="COMPLETED",
            output_payload=output_payload_result,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="onboarding_step_run",
            resource_id=step_uuid,
            version_id=None,
            event_type="ONBOARDING_STEP_COMPLETED",
            change_type="UPDATE",
            principal_id=principal_id,
            justification="step completed",
            schema_version=1,
        )
        all_steps = await self.repository.list_onboarding_steps(version.onboarding_version_id)
        current_step_index = next(
            (
                i
                for i, s in enumerate(all_steps)
                if s.onboarding_step_id == step_run.onboarding_step_id
            ),
            None,
        )
        if current_step_index is not None and current_step_index + 1 < len(all_steps):
            next_step_def = all_steps[current_step_index + 1]
            await self.repository.create_step(
                onboarding_run_id=run_uuid,
                onboarding_step_id=next_step_def.onboarding_step_id,
                name=f"Step {current_step_index + 2}",
                schema_id=None,
            )
        return StepRun(
            id=updated_step.step_run_id,
            onboarding_run_id=updated_step.onboarding_run_id,
            onboarding_step_id=updated_step.onboarding_step_id,
            name=updated_step.name,
            status=updated_step.status,
            input_payload=updated_step.input_payload,
            output_payload=updated_step.output_payload,
            schema_id=updated_step.schema_id,
        )
