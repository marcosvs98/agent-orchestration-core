from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class Onboarding(BaseModel):
    id: UUID
    name: str | None = None
    created_by: str | None = None


class OnboardingCreate(BaseModel):
    name: str | None = None


class OnboardingVersion(BaseModel):
    id: UUID
    onboarding_id: UUID
    status: str
    version_major: int
    version_minor: int
    version_patch: int


class OnboardingVersionCreate(BaseModel):
    source_version_id: UUID | None = None
    version_major: int | None = None
    version_minor: int | None = None
    version_patch: int | None = None


class OnboardingRun(BaseModel):
    id: UUID
    onboarding_version_id: UUID


class OnboardingRunCreate(BaseModel):
    onboarding_version_id: UUID


class StepRunStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StepRun(BaseModel):
    id: UUID
    onboarding_run_id: UUID
    onboarding_step_id: UUID
    name: str
    status: str
    input_payload: dict[str, object]
    output_payload: dict[str, object]
    schema_id: UUID | None = None


class StepRunAdvance(BaseModel):
    input_payload: dict[str, object]
