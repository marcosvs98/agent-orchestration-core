from __future__ import annotations

from uuid import UUID

from domain.common.schemas.change import ChangeRequest
from domain.governance.repositories.access_policy_repository import (
    AccessPolicyRepository,
)
from domain.governance.repositories.billing_policy_repository import (
    BillingPolicyRepository,
)
from domain.governance.repositories.memory_policy_repository import (
    MemoryPolicyRepository,
)
from domain.governance.repositories.rag_policy_repository import RagPolicyRepository
from domain.governance.repositories.rate_limit_policy_repository import (
    RateLimitPolicyRepository,
)
from domain.governance.repositories.runtime_policy_repository import (
    RuntimePolicyRepository,
)
from domain.governance.schemas.memory_policy import MemoryPolicyDefinition
from domain.governance.schemas.policy_admin import (
    AccessPolicyCreate,
    AccessPolicyResponse,
    AccessPolicyRules,
    AccessPolicyVersionCreate,
    AccessPolicyVersionResponse,
    BillingPolicyCreate,
    BillingPolicyResponse,
    BillingPolicyRulesSchema,
    BillingPolicyVersionCreate,
    BillingPolicyVersionResponse,
    MemoryPolicyCreate,
    MemoryPolicyResponse,
    MemoryPolicyVersionCreate,
    MemoryPolicyVersionResponse,
    RagPolicyCreate,
    RagPolicyResponse,
    RagPolicyVersionCreate,
    RagPolicyVersionResponse,
    RateLimitPolicyCreate,
    RateLimitPolicyResponse,
    RateLimitPolicyVersionCreate,
    RateLimitPolicyVersionResponse,
    RuntimePolicyCreate,
    RuntimePolicyResponse,
    RuntimePolicyUpdate,
)
from domain.governance.schemas.rag_policy import RagPolicyDefinition
from domain.governance.schemas.runtime_policy import RuntimePolicyDefinition
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)


class GovernancePoliciesService:
    def __init__(
        self,
        runtime_repository: RuntimePolicyRepository,
        access_repository: AccessPolicyRepository,
        rate_limit_repository: RateLimitPolicyRepository,
        billing_repository: BillingPolicyRepository,
        memory_repository: MemoryPolicyRepository,
        rag_repository: RagPolicyRepository,
    ) -> None:
        self.runtime_repository = runtime_repository
        self.access_repository = access_repository
        self.rate_limit_repository = rate_limit_repository
        self.billing_repository = billing_repository
        self.memory_repository = memory_repository
        self.rag_repository = rag_repository

    async def create_runtime_policy(
        self,
        *,
        tenant_id: UUID,
        runtime_policy_create: RuntimePolicyCreate,
        principal_id: str,
    ) -> RuntimePolicyResponse:
        definition = RuntimePolicyDefinition.model_validate(
            runtime_policy_create.policy_definition.model_dump(mode="json")
        ).model_dump(mode="json")
        created = await self.runtime_repository.create_policy(
            tenant_id=tenant_id,
            scope=runtime_policy_create.scope,
            flow_id=runtime_policy_create.flow_id,
            policy_definition=definition,
            created_by=principal_id,
            version=runtime_policy_create.version,
            status="DRAFT",
        )
        return RuntimePolicyResponse(
            id=created.runtime_policy_id,
            tenant_id=created.tenant_id,
            scope=created.scope,
            flow_id=created.flow_id,
            version=created.version,
            status=created.status,
            policy_definition=RuntimePolicyDefinition.model_validate(
                created.policy_definition or {}
            ),
        )

    async def list_runtime_policies(self, *, tenant_id: UUID) -> list[RuntimePolicyResponse]:
        rows = await self.runtime_repository.list_policies(tenant_id=tenant_id)
        return [
            RuntimePolicyResponse(
                id=row.runtime_policy_id,
                tenant_id=row.tenant_id,
                scope=row.scope,
                flow_id=row.flow_id,
                version=row.version,
                status=row.status,
                policy_definition=RuntimePolicyDefinition.model_validate(
                    row.policy_definition or {}
                ),
            )
            for row in rows
        ]

    async def get_runtime_policy(
        self, *, tenant_id: UUID, runtime_policy_id: UUID
    ) -> RuntimePolicyResponse:
        policy = await self.runtime_repository.get_policy(runtime_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="runtime_policy_not_found")
        return RuntimePolicyResponse(
            id=policy.runtime_policy_id,
            tenant_id=policy.tenant_id,
            scope=policy.scope,
            flow_id=policy.flow_id,
            version=policy.version,
            status=policy.status,
            policy_definition=RuntimePolicyDefinition.model_validate(
                policy.policy_definition or {}
            ),
        )

    async def update_runtime_policy(
        self,
        *,
        tenant_id: UUID,
        runtime_policy_id: UUID,
        payload: RuntimePolicyUpdate,
    ) -> RuntimePolicyResponse:
        existing = await self.runtime_repository.get_policy(runtime_policy_id)
        if existing is None or existing.tenant_id != tenant_id:
            raise NotFoundServiceException(message="runtime_policy_not_found")
        policy_definition = (
            RuntimePolicyDefinition.model_validate(
                payload.policy_definition.model_dump(mode="json")
            ).model_dump(mode="json")
            if payload.policy_definition is not None
            else None
        )
        updated = await self.runtime_repository.update_policy(
            runtime_policy_id=runtime_policy_id,
            policy_definition=policy_definition,
            status=payload.status,
        )
        if updated is None:
            raise NotFoundServiceException(message="runtime_policy_not_found")
        return RuntimePolicyResponse(
            id=updated.runtime_policy_id,
            tenant_id=updated.tenant_id,
            scope=updated.scope,
            flow_id=updated.flow_id,
            version=updated.version,
            status=updated.status,
            policy_definition=RuntimePolicyDefinition.model_validate(
                updated.policy_definition or {}
            ),
        )

    async def activate_runtime_policy(
        self,
        *,
        tenant_id: UUID,
        runtime_policy_id: UUID,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RuntimePolicyResponse:
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        policy = await self.runtime_repository.get_policy(runtime_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="runtime_policy_not_found")
        RuntimePolicyDefinition.model_validate(policy.policy_definition or {})
        active = await self.runtime_repository.activate_policy(
            runtime_policy_id=runtime_policy_id,
            principal_id=principal_id,
        )
        return RuntimePolicyResponse(
            id=active.runtime_policy_id,
            tenant_id=active.tenant_id,
            scope=active.scope,
            flow_id=active.flow_id,
            version=active.version,
            status=active.status,
            policy_definition=RuntimePolicyDefinition.model_validate(
                active.policy_definition or {}
            ),
        )

    async def create_access_policy(
        self, *, tenant_id: UUID, payload: AccessPolicyCreate
    ) -> AccessPolicyResponse:
        created = await self.access_repository.create_policy(
            tenant_id=tenant_id,
            name=payload.name,
        )
        return AccessPolicyResponse(
            id=created.access_policy_id,
            tenant_id=created.tenant_id,
            name=created.name,
        )

    async def list_access_policies(self, *, tenant_id: UUID) -> list[AccessPolicyResponse]:
        rows = await self.access_repository.list_policies(tenant_id=tenant_id)
        return [
            AccessPolicyResponse(id=row.access_policy_id, tenant_id=row.tenant_id, name=row.name)
            for row in rows
        ]

    async def get_access_policy(
        self, *, tenant_id: UUID, access_policy_id: UUID
    ) -> AccessPolicyResponse:
        policy = await self.access_repository.get_policy(access_policy_id=access_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="access_policy_not_found")
        return AccessPolicyResponse(
            id=policy.access_policy_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
        )

    async def create_access_policy_version(
        self, *, tenant_id: UUID, access_policy_id: UUID, payload: AccessPolicyVersionCreate
    ) -> AccessPolicyVersionResponse:
        policy = await self.access_repository.get_policy(access_policy_id=access_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="access_policy_not_found")
        rules_dict = payload.rules.model_dump(mode="json", exclude_none=True)
        created = await self.access_repository.create_version(
            access_policy_id=access_policy_id,
            rules=rules_dict,
            status=payload.status,
            version_major=payload.version_major,
            version_minor=payload.version_minor,
            version_patch=payload.version_patch,
        )
        return AccessPolicyVersionResponse(
            id=created.access_policy_version_id,
            access_policy_id=created.access_policy_id,
            status=created.status,
            version_major=created.version_major,
            version_minor=created.version_minor,
            version_patch=created.version_patch,
            rules=AccessPolicyRules.model_validate(created.rules or {}),
        )

    async def publish_access_policy_version(
        self, *, tenant_id: UUID, access_policy_version_id: UUID
    ) -> AccessPolicyVersionResponse:
        version = await self.access_repository.get_version(
            access_policy_version_id=access_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="access_policy_version_not_found")
        policy = await self.access_repository.get_policy(access_policy_id=version.access_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="access_policy_version_not_found")
        await self.access_repository.set_version_status(
            access_policy_version_id=access_policy_version_id, status="PUBLISHED"
        )
        version = await self.access_repository.get_version(
            access_policy_version_id=access_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="access_policy_version_not_found")
        return AccessPolicyVersionResponse(
            id=version.access_policy_version_id,
            access_policy_id=version.access_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            rules=AccessPolicyRules.model_validate(version.rules or {}),
        )

    async def create_rate_limit_policy(
        self, *, tenant_id: UUID, payload: RateLimitPolicyCreate
    ) -> RateLimitPolicyResponse:
        created = await self.rate_limit_repository.create_policy(
            tenant_id=tenant_id,
            name=payload.name,
        )
        return RateLimitPolicyResponse(
            id=created.rate_limit_policy_id,
            tenant_id=created.tenant_id,
            name=created.name,
        )

    async def list_rate_limit_policies(self, *, tenant_id: UUID) -> list[RateLimitPolicyResponse]:
        rows = await self.rate_limit_repository.list_policies(tenant_id=tenant_id)
        return [
            RateLimitPolicyResponse(
                id=row.rate_limit_policy_id,
                tenant_id=row.tenant_id,
                name=row.name,
            )
            for row in rows
        ]

    async def get_rate_limit_policy(
        self, *, tenant_id: UUID, rate_limit_policy_id: UUID
    ) -> RateLimitPolicyResponse:
        policy = await self.rate_limit_repository.get_policy(
            rate_limit_policy_id=rate_limit_policy_id
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rate_limit_policy_not_found")
        return RateLimitPolicyResponse(
            id=policy.rate_limit_policy_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
        )

    async def create_rate_limit_policy_version(
        self,
        *,
        tenant_id: UUID,
        rate_limit_policy_id: UUID,
        payload: RateLimitPolicyVersionCreate,
    ) -> RateLimitPolicyVersionResponse:
        policy = await self.rate_limit_repository.get_policy(
            rate_limit_policy_id=rate_limit_policy_id
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rate_limit_policy_not_found")
        created = await self.rate_limit_repository.create_version(
            rate_limit_policy_id=rate_limit_policy_id,
            status=payload.status,
            version_major=payload.version_major,
            version_minor=payload.version_minor,
            version_patch=payload.version_patch,
            action=payload.action,
            principal_type=payload.principal_type,
            limit=payload.limit,
            window_seconds=payload.window_seconds,
        )
        return RateLimitPolicyVersionResponse(
            id=created.rate_limit_policy_version_id,
            rate_limit_policy_id=created.rate_limit_policy_id,
            status=created.status,
            version_major=created.version_major,
            version_minor=created.version_minor,
            version_patch=created.version_patch,
            action=created.action,
            principal_type=created.principal_type,
            limit=created.limit,
            window_seconds=created.window_seconds,
        )

    async def publish_rate_limit_policy_version(
        self, *, tenant_id: UUID, rate_limit_policy_version_id: UUID
    ) -> RateLimitPolicyVersionResponse:
        version = await self.rate_limit_repository.get_version(
            rate_limit_policy_version_id=rate_limit_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="rate_limit_policy_version_not_found")
        policy = await self.rate_limit_repository.get_policy(
            rate_limit_policy_id=version.rate_limit_policy_id
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rate_limit_policy_version_not_found")
        await self.rate_limit_repository.set_version_status(
            rate_limit_policy_version_id=rate_limit_policy_version_id,
            status="PUBLISHED",
        )
        version = await self.rate_limit_repository.get_version(
            rate_limit_policy_version_id=rate_limit_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="rate_limit_policy_version_not_found")
        return RateLimitPolicyVersionResponse(
            id=version.rate_limit_policy_version_id,
            rate_limit_policy_id=version.rate_limit_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            action=version.action,
            principal_type=version.principal_type,
            limit=version.limit,
            window_seconds=version.window_seconds,
        )

    async def create_billing_policy(
        self, *, tenant_id: UUID, payload: BillingPolicyCreate
    ) -> BillingPolicyResponse:
        created = await self.billing_repository.create_policy(
            tenant_id=tenant_id,
            name=payload.name,
        )
        return BillingPolicyResponse(
            id=created.billing_policy_id,
            tenant_id=created.tenant_id,
            name=created.name,
        )

    async def list_billing_policies(self, *, tenant_id: UUID) -> list[BillingPolicyResponse]:
        rows = await self.billing_repository.list_policies(tenant_id=tenant_id)
        return [
            BillingPolicyResponse(
                id=row.billing_policy_id,
                tenant_id=row.tenant_id,
                name=row.name,
            )
            for row in rows
        ]

    async def get_billing_policy(
        self, *, tenant_id: UUID, billing_policy_id: UUID
    ) -> BillingPolicyResponse:
        policy = await self.billing_repository.get_policy(billing_policy_id=billing_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="billing_policy_not_found")
        return BillingPolicyResponse(
            id=policy.billing_policy_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
        )

    async def create_billing_policy_version(
        self, *, tenant_id: UUID, billing_policy_id: UUID, payload: BillingPolicyVersionCreate
    ) -> BillingPolicyVersionResponse:
        policy = await self.billing_repository.get_policy(billing_policy_id=billing_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="billing_policy_not_found")
        created = await self.billing_repository.create_version(
            billing_policy_id=billing_policy_id,
            status=payload.status,
            version_major=payload.version_major,
            version_minor=payload.version_minor,
            version_patch=payload.version_patch,
            rules=payload.rules.model_dump(mode="json", exclude_none=True),
        )
        return BillingPolicyVersionResponse(
            id=created.billing_policy_version_id,
            billing_policy_id=created.billing_policy_id,
            status=created.status,
            version_major=created.version_major,
            version_minor=created.version_minor,
            version_patch=created.version_patch,
            rules=BillingPolicyRulesSchema.model_validate(created.rules or {}),
        )

    async def publish_billing_policy_version(
        self, *, tenant_id: UUID, billing_policy_version_id: UUID
    ) -> BillingPolicyVersionResponse:
        version = await self.billing_repository.get_version(
            billing_policy_version_id=billing_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="billing_policy_version_not_found")
        policy = await self.billing_repository.get_policy(
            billing_policy_id=version.billing_policy_id
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="billing_policy_version_not_found")
        await self.billing_repository.set_version_status(
            billing_policy_version_id=billing_policy_version_id,
            status="PUBLISHED",
        )
        version = await self.billing_repository.get_version(
            billing_policy_version_id=billing_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="billing_policy_version_not_found")
        return BillingPolicyVersionResponse(
            id=version.billing_policy_version_id,
            billing_policy_id=version.billing_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            rules=BillingPolicyRulesSchema.model_validate(version.rules or {}),
        )

    async def activate_billing_policy_version(
        self,
        *,
        tenant_id: UUID,
        billing_policy_version_id: UUID,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> BillingPolicyVersionResponse:
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        version = await self.billing_repository.get_version(
            billing_policy_version_id=billing_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="billing_policy_version_not_found")
        policy = await self.billing_repository.get_policy(
            billing_policy_id=version.billing_policy_id
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="billing_policy_version_not_found")
        await self.billing_repository.set_active_version(
            tenant_id=tenant_id,
            billing_policy_version_id=billing_policy_version_id,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
        )
        return BillingPolicyVersionResponse(
            id=version.billing_policy_version_id,
            billing_policy_id=version.billing_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            rules=BillingPolicyRulesSchema.model_validate(version.rules or {}),
        )

    async def create_memory_policy(
        self, *, tenant_id: UUID, payload: MemoryPolicyCreate
    ) -> MemoryPolicyResponse:
        created = await self.memory_repository.create_policy(
            tenant_id=tenant_id,
            name=payload.name,
        )
        return MemoryPolicyResponse(
            id=created.memory_policy_id,
            tenant_id=created.tenant_id,
            name=created.name,
        )

    async def list_memory_policies(self, *, tenant_id: UUID) -> list[MemoryPolicyResponse]:
        rows = await self.memory_repository.list_policies(tenant_id=tenant_id)
        return [
            MemoryPolicyResponse(
                id=row.memory_policy_id,
                tenant_id=row.tenant_id,
                name=row.name,
            )
            for row in rows
        ]

    async def get_memory_policy(
        self, *, tenant_id: UUID, memory_policy_id: UUID
    ) -> MemoryPolicyResponse:
        policy = await self.memory_repository.get_policy(memory_policy_id=memory_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="memory_policy_not_found")
        return MemoryPolicyResponse(
            id=policy.memory_policy_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
        )

    async def create_memory_policy_version(
        self, *, tenant_id: UUID, memory_policy_id: UUID, payload: MemoryPolicyVersionCreate
    ) -> MemoryPolicyVersionResponse:
        policy = await self.memory_repository.get_policy(memory_policy_id=memory_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="memory_policy_not_found")
        definition = MemoryPolicyDefinition.model_validate(
            payload.definition.model_dump(mode="json")
        )
        created = await self.memory_repository.create_version(
            memory_policy_id=memory_policy_id,
            status=payload.status,
            version_major=payload.version_major,
            version_minor=payload.version_minor,
            version_patch=payload.version_patch,
            retention_ttl_seconds=definition.retention_ttl_seconds,
            consent_definition=definition.consent.model_dump(mode="json"),
            allowed_sources=[item.value for item in definition.allowed_sources],
            allowed_schemas=[item.model_dump(mode="json") for item in definition.allowed_schemas],
        )
        return MemoryPolicyVersionResponse(
            id=created.memory_policy_version_id,
            memory_policy_id=created.memory_policy_id,
            status=created.status,
            version_major=created.version_major,
            version_minor=created.version_minor,
            version_patch=created.version_patch,
            definition=definition,
        )

    async def publish_memory_policy_version(
        self, *, tenant_id: UUID, memory_policy_version_id: UUID
    ) -> MemoryPolicyVersionResponse:
        version = await self.memory_repository.get_version(
            memory_policy_version_id=memory_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="memory_policy_version_not_found")
        policy = await self.memory_repository.get_policy(memory_policy_id=version.memory_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="memory_policy_version_not_found")
        await self.memory_repository.set_version_status(
            memory_policy_version_id=memory_policy_version_id,
            status="PUBLISHED",
        )
        version = await self.memory_repository.get_version(
            memory_policy_version_id=memory_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="memory_policy_version_not_found")
        definition = MemoryPolicyDefinition(
            retention_ttl_seconds=int(version.retention_ttl_seconds),
            consent=version.consent_definition or {},
            allowed_sources=version.allowed_sources or [],
            allowed_schemas=version.allowed_schemas or [],
        )
        return MemoryPolicyVersionResponse(
            id=version.memory_policy_version_id,
            memory_policy_id=version.memory_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            definition=definition,
        )

    async def activate_memory_policy_version(
        self,
        *,
        tenant_id: UUID,
        memory_policy_version_id: UUID,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> MemoryPolicyVersionResponse:
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        version = await self.memory_repository.get_version(
            memory_policy_version_id=memory_policy_version_id
        )
        if version is None:
            raise NotFoundServiceException(message="memory_policy_version_not_found")
        policy = await self.memory_repository.get_policy(memory_policy_id=version.memory_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="memory_policy_version_not_found")
        await self.memory_repository.set_active_version(
            tenant_id=tenant_id,
            memory_policy_version_id=memory_policy_version_id,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
        )
        definition = MemoryPolicyDefinition(
            retention_ttl_seconds=int(version.retention_ttl_seconds),
            consent=version.consent_definition or {},
            allowed_sources=version.allowed_sources or [],
            allowed_schemas=version.allowed_schemas or [],
        )
        return MemoryPolicyVersionResponse(
            id=version.memory_policy_version_id,
            memory_policy_id=version.memory_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            definition=definition,
        )

    async def create_rag_policy(
        self, *, tenant_id: UUID, payload: RagPolicyCreate
    ) -> RagPolicyResponse:
        created = await self.rag_repository.create_policy(tenant_id=tenant_id, name=payload.name)
        return RagPolicyResponse(
            id=created.rag_policy_id, tenant_id=created.tenant_id, name=created.name
        )

    async def list_rag_policies(self, *, tenant_id: UUID) -> list[RagPolicyResponse]:
        rows = await self.rag_repository.list_policies(tenant_id=tenant_id)
        return [
            RagPolicyResponse(
                id=row.rag_policy_id,
                tenant_id=row.tenant_id,
                name=row.name,
            )
            for row in rows
        ]

    async def get_rag_policy(self, *, tenant_id: UUID, rag_policy_id: UUID) -> RagPolicyResponse:
        policy = await self.rag_repository.get_policy(rag_policy_id=rag_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_policy_not_found")
        return RagPolicyResponse(
            id=policy.rag_policy_id,
            tenant_id=policy.tenant_id,
            name=policy.name,
        )

    async def create_rag_policy_version(
        self, *, tenant_id: UUID, rag_policy_id: UUID, payload: RagPolicyVersionCreate
    ) -> RagPolicyVersionResponse:
        policy = await self.rag_repository.get_policy(rag_policy_id=rag_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_policy_not_found")
        definition = RagPolicyDefinition.model_validate(payload.definition.model_dump(mode="json"))
        created = await self.rag_repository.create_version(
            rag_policy_id=rag_policy_id,
            status=payload.status,
            version_major=payload.version_major,
            version_minor=payload.version_minor,
            version_patch=payload.version_patch,
            policy_definition=definition.model_dump(mode="json"),
        )
        return RagPolicyVersionResponse(
            id=created.rag_policy_version_id,
            rag_policy_id=created.rag_policy_id,
            status=created.status,
            version_major=created.version_major,
            version_minor=created.version_minor,
            version_patch=created.version_patch,
            definition=definition,
        )

    async def publish_rag_policy_version(
        self, *, tenant_id: UUID, rag_policy_version_id: UUID
    ) -> RagPolicyVersionResponse:
        version = await self.rag_repository.get_version(rag_policy_version_id=rag_policy_version_id)
        if version is None:
            raise NotFoundServiceException(message="rag_policy_version_not_found")
        policy = await self.rag_repository.get_policy(rag_policy_id=version.rag_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_policy_version_not_found")
        await self.rag_repository.set_version_status(
            rag_policy_version_id=rag_policy_version_id,
            status="PUBLISHED",
        )
        version = await self.rag_repository.get_version(rag_policy_version_id=rag_policy_version_id)
        if version is None:
            raise NotFoundServiceException(message="rag_policy_version_not_found")
        definition = RagPolicyDefinition.model_validate(version.policy_definition or {})
        return RagPolicyVersionResponse(
            id=version.rag_policy_version_id,
            rag_policy_id=version.rag_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            definition=definition,
        )

    async def activate_rag_policy_version(
        self,
        *,
        tenant_id: UUID,
        rag_policy_version_id: UUID,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RagPolicyVersionResponse:
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        version = await self.rag_repository.get_version(rag_policy_version_id=rag_policy_version_id)
        if version is None:
            raise NotFoundServiceException(message="rag_policy_version_not_found")
        policy = await self.rag_repository.get_policy(rag_policy_id=version.rag_policy_id)
        if policy is None or policy.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_policy_version_not_found")
        await self.rag_repository.set_active_version(
            tenant_id=tenant_id,
            rag_policy_version_id=rag_policy_version_id,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
        )
        definition = RagPolicyDefinition.model_validate(version.policy_definition or {})
        return RagPolicyVersionResponse(
            id=version.rag_policy_version_id,
            rag_policy_id=version.rag_policy_id,
            status=version.status,
            version_major=version.version_major,
            version_minor=version.version_minor,
            version_patch=version.version_patch,
            definition=definition,
        )
