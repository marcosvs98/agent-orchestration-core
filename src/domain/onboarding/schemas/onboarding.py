from uuid import UUID

from pydantic import BaseModel


class Onboarding(BaseModel):
    id: UUID
    name: str | None = None


class OnboardingCreate(BaseModel):
    name: str | None = None


class OnboardingVersion(BaseModel):
    id: UUID
    onboarding_id: UUID


class OnboardingRun(BaseModel):
    id: UUID
    onboarding_version_id: UUID


class OnboardingRunCreate(BaseModel):
    onboarding_version_id: UUID
