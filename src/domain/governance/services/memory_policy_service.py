from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.schemas.memory_policy import (
    AllowedSchema,
    ConsentDefinition,
    MemoryPolicyDefinition,
    MemoryPolicySource,
    ResolvedMemoryPolicy,
    ResolvedMemoryPolicySource,
    UserMemoryItem,
)
from exceptions.service_exceptions import AuthorizationDeniedException, DomainValidationException


class MemoryPolicyService:
    def __init__(self, repository: ExecutionRepository) -> None:
        self.repository = repository

    async def resolve(self, *, tenant_id: UUID) -> ResolvedMemoryPolicy:
        policy_version_id = await self.repository.get_active_memory_policy_version_id(tenant_id)
        if policy_version_id is None:
            return ResolvedMemoryPolicy(
                source=ResolvedMemoryPolicySource.DEFAULT_NONE,
                tenant_id=tenant_id,
                policy_version_id=None,
                definition=None,
            )
        policy_version = await self.repository.get_memory_policy_version(policy_version_id)
        if policy_version is None:
            return ResolvedMemoryPolicy(
                source=ResolvedMemoryPolicySource.DEFAULT_NONE,
                tenant_id=tenant_id,
                policy_version_id=None,
                definition=None,
            )
        definition = MemoryPolicyDefinition(
            retention_ttl_seconds=int(policy_version.retention_ttl_seconds),
            consent=ConsentDefinition.model_validate(policy_version.consent_definition or {}),
            allowed_sources=[
                MemoryPolicySource(value)
                for value in list(policy_version.allowed_sources or [])
            ],
            allowed_schemas=[
                AllowedSchema.model_validate(item)
                for item in list(policy_version.allowed_schemas or [])
            ],
        )
        return ResolvedMemoryPolicy(
            source=ResolvedMemoryPolicySource.TENANT_ACTIVE,
            tenant_id=tenant_id,
            policy_version_id=policy_version.memory_policy_version_id,
            definition=definition,
        )

    async def enforce_write(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        item: UserMemoryItem,
    ) -> tuple[ResolvedMemoryPolicy, datetime | None]:
        resolved_policy = await self.resolve(tenant_id=tenant_id)
        if resolved_policy.definition is None:
            if item.source == MemoryPolicySource.INFERRED_LLM:
                raise AuthorizationDeniedException(
                    message="memory_policy_required_for_inferred_memory"
                )
            return resolved_policy, None

        definition = resolved_policy.definition
        self._validate_allowed_source(definition=definition, source=item.source)
        schema = self._validate_allowed_schema(
            definition=definition,
            schema_id=item.schema_id,
        )
        self._validate_schema_payload(schema=schema, payload=item.data)
        await self._enforce_consent(
            tenant_id=tenant_id,
            user_id=user_id,
            definition=definition,
            source=item.source,
        )
        ttl_seconds = int(definition.retention_ttl_seconds)
        if ttl_seconds <= 0:
            raise DomainValidationException(message="invalid_memory_policy_ttl")
        base_time = item.observed_at or datetime.now(UTC)
        expires_at = base_time + timedelta(seconds=ttl_seconds)
        return resolved_policy, expires_at

    def _validate_allowed_source(
        self,
        *,
        definition: MemoryPolicyDefinition,
        source: MemoryPolicySource,
    ) -> None:
        allowed_sources = definition.allowed_sources
        if allowed_sources and source not in allowed_sources:
            raise AuthorizationDeniedException(message="memory_source_not_allowed")

    def _validate_allowed_schema(
        self,
        *,
        definition: MemoryPolicyDefinition,
        schema_id: str,
    ) -> AllowedSchema | None:
        allowed_schemas = definition.allowed_schemas
        if not allowed_schemas:
            return None
        for allowed_schema in allowed_schemas:
            if allowed_schema.schema_id == schema_id:
                return allowed_schema
        raise AuthorizationDeniedException(message="memory_schema_not_allowed")

    def _validate_schema_payload(
        self,
        *,
        schema: AllowedSchema | None,
        payload: dict[str, object],
    ) -> None:
        if schema is None:
            return
        if schema.max_item_bytes is not None:
            payload_size = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
            if payload_size > int(schema.max_item_bytes):
                raise DomainValidationException(message="memory_item_too_large")
        allow_fields = schema.allow_fields or {}
        allowed_field_names = allow_fields.get("allowed")
        if isinstance(allowed_field_names, list):
            allowed_set = {str(field_name) for field_name in allowed_field_names}
            unexpected_fields = set(payload.keys()) - allowed_set
            if unexpected_fields:
                raise DomainValidationException(message="memory_item_fields_not_allowed")

    async def _enforce_consent(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        definition: MemoryPolicyDefinition,
        source: MemoryPolicySource,
    ) -> None:
        consent_definition = definition.consent
        requires_consent = bool(consent_definition.required) or (
            source in consent_definition.required_for_sources
        )
        if not requires_consent:
            return
        preferences = await self.repository.get_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        consent_value = preferences.get(consent_definition.preference_key)
        if not self._is_consent_granted(consent_value):
            raise AuthorizationDeniedException(message="memory_consent_not_granted")

    def _is_consent_granted(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, dict):
            granted = value.get("granted")
            if isinstance(granted, bool):
                return granted
            enabled = value.get("enabled")
            if isinstance(enabled, bool):
                return enabled
        return False
