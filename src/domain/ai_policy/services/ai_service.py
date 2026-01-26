from uuid import UUID

from domain.ai_policy.ports.service import AIServicePort
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.ai_policy.schemas.ai import (
    AITask,
    AIExecutionPolicy,
    AIExecutionPolicyCreate,
    AIExecutionPolicyVersion,
    AIExecutionPolicyVersionCreate,
    Model,
)
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class AIService(AIServicePort):
    def __init__(
        self,
        repository: AIRepository,
        authoring_events: AuthoringEventRepository,
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def list_ai_tasks(self) -> list[AITask]:
        tasks = await self.repository.list_ai_tasks()
        return [AITask(id=task.ai_task_id, name=task.name) for task in tasks]

    async def create_ai_execution_policy(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_create: AIExecutionPolicyCreate,
        principal_id: str,
    ) -> AIExecutionPolicy:
        model = await self.repository.create_ai_execution_policy(
            tenant_id=tenant_id,
            description=ai_execution_policy_create.description,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="ai_execution_policy",
            resource_id=model.ai_execution_policy_id,
            version_id=None,
            event_type="AI_EXECUTION_POLICY_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create ai execution policy",
            schema_version=1,
        )
        return AIExecutionPolicy(
            id=model.ai_execution_policy_id, description=model.description
        )

    async def create_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_version_create: AIExecutionPolicyVersionCreate,
        principal_id: str,
    ) -> AIExecutionPolicyVersion:
        policy_uuid = ai_execution_policy_version_create.ai_execution_policy_id
        policy = await self.repository.get_ai_execution_policy(policy_uuid)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="ai_execution_policy_not_found")
        model = await self.repository.get_model(
            ai_execution_policy_version_create.model_id
        )
        if model is None:
            raise NotFoundServiceException(message="model_not_found")
        version_model = await self.repository.create_ai_execution_policy_version(
            ai_execution_policy_id=policy_uuid,
            source_version_id=ai_execution_policy_version_create.source_version_id,
            model_id=ai_execution_policy_version_create.model_id,
            version_major=ai_execution_policy_version_create.version_major,
            version_minor=ai_execution_policy_version_create.version_minor,
            version_patch=ai_execution_policy_version_create.version_patch,
            config_hash=None,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="ai_execution_policy",
            resource_id=policy_uuid,
            version_id=version_model.ai_execution_policy_version_id,
            event_type="AI_EXECUTION_POLICY_VERSION_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create ai execution policy version",
            schema_version=1,
        )
        return AIExecutionPolicyVersion(
            id=version_model.ai_execution_policy_version_id,
            ai_execution_policy_id=version_model.ai_execution_policy_id,
            model_id=version_model.model_id,
            notes=None,
            status=version_model.status,
            version_major=version_model.version_major,
            version_minor=version_model.version_minor,
            version_patch=version_model.version_patch,
            config_hash=version_model.config_hash,
        )

    async def validate_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
    ) -> AIExecutionPolicyVersion:
        policy_uuid = UUID(ai_execution_policy_id)
        version_uuid = UUID(ai_execution_policy_version_id)
        policy = await self.repository.get_ai_execution_policy(policy_uuid)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="ai_execution_policy_not_found")
        version = await self.repository.get_ai_execution_policy_version(version_uuid)
        if version is None or version.ai_execution_policy_id != policy_uuid:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        if version.status != VersionStatus.DRAFT:
            raise ResourceBlockedServiceException(
                message="ai_execution_policy_version_not_draft"
            )
        await self.repository.set_ai_execution_policy_version_status(
            ai_execution_policy_version_id=version_uuid, status=VersionStatus.VALIDATED
        )
        refreshed = await self.repository.get_ai_execution_policy_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        return AIExecutionPolicyVersion(
            id=refreshed.ai_execution_policy_version_id,
            ai_execution_policy_id=refreshed.ai_execution_policy_id,
            model_id=refreshed.model_id,
            notes=None,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def list_models(self) -> list[Model]:
        models = await self.repository.list_models()
        return [Model(id=model.model_id, name=model.name) for model in models]

    async def list_ai_execution_policy_versions(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str | None = None,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[AIExecutionPolicyVersion]:
        policy_uuid = UUID(ai_execution_policy_id) if ai_execution_policy_id else None
        if policy_uuid is not None:
            policy = await self.repository.get_ai_execution_policy(policy_uuid)
            if policy is None or policy.tenant_id != tenant_id:
                raise NotFoundServiceException(message="ai_execution_policy_not_found")
        versions = await self.repository.list_ai_execution_policy_versions(
            tenant_id=tenant_id,
            ai_execution_policy_id=policy_uuid,
            status_filter=status_filter,
            limit=limit,
        )
        return [
            AIExecutionPolicyVersion(
                id=version.ai_execution_policy_version_id,
                ai_execution_policy_id=version.ai_execution_policy_id,
                model_id=version.model_id,
                notes=None,
                status=version.status,
                version_major=version.version_major,
                version_minor=version.version_minor,
                version_patch=version.version_patch,
                config_hash=version.config_hash,
            )
            for version in versions
        ]

    async def publish_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        policy_uuid = UUID(ai_execution_policy_id)
        version_uuid = UUID(ai_execution_policy_version_id)
        policy = await self.repository.get_ai_execution_policy(policy_uuid)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="ai_execution_policy_not_found")
        version = await self.repository.get_ai_execution_policy_version(version_uuid)
        if version is None or version.ai_execution_policy_id != policy_uuid:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        if version.status != VersionStatus.VALIDATED:
            raise ResourceBlockedServiceException(
                message="ai_execution_policy_version_not_validated"
            )
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_ai_execution_policy_version_status(
            ai_execution_policy_version_id=version_uuid, status=VersionStatus.PUBLISHED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="ai_execution_policy",
            resource_id=policy_uuid,
            version_id=version_uuid,
            event_type="VERSION_PUBLISHED",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_ai_execution_policy_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        return AIExecutionPolicyVersion(
            id=refreshed.ai_execution_policy_version_id,
            ai_execution_policy_id=refreshed.ai_execution_policy_id,
            model_id=refreshed.model_id,
            notes=None,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def deprecate_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        policy_uuid = UUID(ai_execution_policy_id)
        version_uuid = UUID(ai_execution_policy_version_id)
        policy = await self.repository.get_ai_execution_policy(policy_uuid)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="ai_execution_policy_not_found")
        version = await self.repository.get_ai_execution_policy_version(version_uuid)
        if version is None or version.ai_execution_policy_id != policy_uuid:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(
                message="ai_execution_policy_version_not_published"
            )
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_ai_execution_policy_version_status(
            ai_execution_policy_version_id=version_uuid, status=VersionStatus.DEPRECATED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="ai_execution_policy",
            resource_id=policy_uuid,
            version_id=version_uuid,
            event_type="VERSION_DEPRECATED",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_ai_execution_policy_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        return AIExecutionPolicyVersion(
            id=refreshed.ai_execution_policy_version_id,
            ai_execution_policy_id=refreshed.ai_execution_policy_id,
            model_id=refreshed.model_id,
            notes=None,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def disable_ai_execution_policy_version(
        self,
        *,
        tenant_id: UUID,
        ai_execution_policy_id: str,
        ai_execution_policy_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> AIExecutionPolicyVersion:
        policy_uuid = UUID(ai_execution_policy_id)
        version_uuid = UUID(ai_execution_policy_version_id)
        policy = await self.repository.get_ai_execution_policy(policy_uuid)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="ai_execution_policy_not_found")
        version = await self.repository.get_ai_execution_policy_version(version_uuid)
        if version is None or version.ai_execution_policy_id != policy_uuid:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        if version.status not in (VersionStatus.PUBLISHED, VersionStatus.DEPRECATED):
            raise ResourceBlockedServiceException(
                message="ai_execution_policy_version_not_published_or_deprecated"
            )
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_ai_execution_policy_version_status(
            ai_execution_policy_version_id=version_uuid, status=VersionStatus.DISABLED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="ai_execution_policy",
            resource_id=policy_uuid,
            version_id=version_uuid,
            event_type="VERSION_DISABLED",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_ai_execution_policy_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(
                message="ai_execution_policy_version_not_found"
            )
        return AIExecutionPolicyVersion(
            id=refreshed.ai_execution_policy_version_id,
            ai_execution_policy_id=refreshed.ai_execution_policy_id,
            model_id=refreshed.model_id,
            notes=None,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )
