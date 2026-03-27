from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import settings
from domain.context.schemas.context_layers import ContextLayerScope
from domain.context.schemas.memory_write import (
    MemoryPreferenceWriteOutcome,
    MemoryWriteEventContext,
    MemoryWriteResult,
    PreferenceKeyDerivationReason,
)
from domain.rag.schemas.rag import RagDocument
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.governance.schemas.memory_policy import (
    AllowedSchema,
    MemoryPolicySource,
    MemoryWriteTarget,
    PreferenceUpdatePolicy,
    UserMemoryItem,
)
from domain.governance.services.memory_policy_service import MemoryPolicyService
from domain.rag.ports.queue import EmbeddingJobQueuePort
from domain.rag.schemas.embedding_job import EmbeddingJobPayload, EmbeddingStatus
from domain.rag.schemas.rag import RagDocumentCreate, RagUserMemoryDocumentType
from domain.rag.services.rag_runtime_service import RagRuntimeService
from exceptions.service_exceptions import DomainValidationException


class MemoryWriteService:
    SOURCE_PRIORITY_MAP: dict[MemoryPolicySource, int] = {
        MemoryPolicySource.EXPLICIT_USER: 4,
        MemoryPolicySource.ADMIN_SEED: 3,
        MemoryPolicySource.TOOL_OUTPUT: 2,
        MemoryPolicySource.INFERRED_LLM: 1,
    }

    def __init__(
        self,
        policy_service: MemoryPolicyService,
        rag_runtime_service: RagRuntimeService,
        repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
        embedding_job_queue: EmbeddingJobQueuePort | None = None,
    ) -> None:
        self.policy_service = policy_service
        self.rag_runtime_service = rag_runtime_service
        self.repository = repository
        self.tracer = tracer
        self.embedding_job_queue = embedding_job_queue

    async def write_memory_item(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        item: dict,
        event_context: MemoryWriteEventContext | None = None,
    ) -> MemoryWriteResult:
        memory_item: UserMemoryItem = UserMemoryItem.model_validate(item)
        resolved_policy, expires_at = await self.policy_service.enforce_write(
            tenant_id=tenant_id,
            user_id=user_id,
            item=memory_item,
        )

        targets: list[MemoryWriteTarget] = self._resolve_write_targets(
            item=memory_item,
            default_target=MemoryWriteTarget.USER_MEMORY_VECTOR,
            policy_schemas=(
                resolved_policy.definition.allowed_schemas
                if resolved_policy.definition
                else []
            ),
        )
        result: MemoryWriteResult = MemoryWriteResult(
            targets_applied=[],
            policy_version_id=resolved_policy.policy_version_id,
        )
        allowed_schema: AllowedSchema = self._find_allowed_schema(
            schema_id=memory_item.schema_id,
            policy_schemas=(
                resolved_policy.definition.allowed_schemas
                if resolved_policy.definition
                else []
            ),
        )

        if MemoryWriteTarget.USER_PREFERENCE in targets:
            preference_policy = (
                allowed_schema.preference_update if allowed_schema is not None else None
            )
            preference_key, derivation_reason = self._derive_preference_key(
                memory_item=memory_item,
                preference_policy=preference_policy,
            )
            if preference_key is None:
                await self._emit_memory_updated_outcome(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    memory_item=memory_item,
                    event_context=event_context,
                    policy_version_id=resolved_policy.policy_version_id,
                    preference_key=self._extract_payload_preference_key(memory_item),
                    outcome=MemoryPreferenceWriteOutcome.IGNORED.value,
                    reason=derivation_reason.value,
                    new_version=None,
                )
            else:
                has_value, preference_value = self._extract_preference_value(
                    memory_item
                )
                if not has_value:
                    await self._emit_memory_updated_outcome(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        memory_item=memory_item,
                        event_context=event_context,
                        policy_version_id=resolved_policy.policy_version_id,
                        preference_key=preference_key,
                        outcome=MemoryPreferenceWriteOutcome.IGNORED.value,
                        reason=PreferenceKeyDerivationReason.MISSING_VALUE.value,
                        new_version=None,
                    )
                else:
                    deterministic_result = (
                        await self.repository.upsert_user_preference_deterministic(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            preference_key=preference_key,
                            preference_value=preference_value,
                            source=memory_item.source.value,
                            source_priority_map=self._source_priority_values(),
                            ignore_if_unchanged=(
                                preference_policy.ignore_if_unchanged
                                if preference_policy is not None
                                else True
                            ),
                        )
                    )
                    if deterministic_result.updated:
                        result.preference_version = deterministic_result.version
                        result.targets_applied.append(MemoryWriteTarget.USER_PREFERENCE)
                        await self._emit_memory_updated_outcome(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            memory_item=memory_item,
                            event_context=event_context,
                            policy_version_id=resolved_policy.policy_version_id,
                            preference_key=preference_key,
                            outcome=MemoryPreferenceWriteOutcome.APPLIED.value,
                            reason=derivation_reason.value,
                            new_version=deterministic_result.version,
                        )
                    else:
                        ignore_reason = (
                            deterministic_result.reason
                            or PreferenceKeyDerivationReason.SOURCE_PRIORITY_DENIED.value
                        )
                        await self._emit_memory_updated_outcome(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            memory_item=memory_item,
                            event_context=event_context,
                            policy_version_id=resolved_policy.policy_version_id,
                            preference_key=preference_key,
                            outcome=MemoryPreferenceWriteOutcome.IGNORED.value,
                            reason=ignore_reason,
                            new_version=None,
                        )

        if MemoryWriteTarget.USER_MEMORY_PROFILE in targets:
            profile_patch = memory_item.data.get("profile_patch")
            if not isinstance(profile_patch, dict):
                raise DomainValidationException(message="memory_profile_patch_required")
            current_profile: dict = await self.repository.get_user_memory_profile(
                tenant_id=tenant_id,
                user_id=user_id,
            )
            merged_profile = self._deep_merge(
                left=current_profile if isinstance(current_profile, dict) else {},
                right=profile_patch,
            )
            profile_version = await self.repository.upsert_user_memory_profile(
                tenant_id=tenant_id,
                user_id=user_id,
                profile=merged_profile,
            )
            result.profile_version = profile_version
            result.targets_applied.append(MemoryWriteTarget.USER_MEMORY_PROFILE)
            event_payload = {
                "scope": ContextLayerScope.USER_MEMORY.value,
                "target": MemoryWriteTarget.USER_MEMORY_PROFILE.value,
                "schema_id": memory_item.schema_id,
                "schema_version": memory_item.schema_version,
                "source": memory_item.source.value,
                "policy_version_id": str(resolved_policy.policy_version_id)
                if resolved_policy.policy_version_id
                else None,
                "profile_version": profile_version,
            }
            await self._append_execution_event(
                tenant_id=tenant_id,
                event_context=event_context,
                event_type=ExecutionEventType.MemoryUpdated,
                payload=event_payload,
            )

        if MemoryWriteTarget.USER_MEMORY_VECTOR in targets:
            cap: dict = (
                await self.rag_runtime_service.resolve_user_memory_vector_document_cap(
                    tenant_id=tenant_id,
                )
            )
            current_count: int = await self.rag_runtime_service.count_user_memory_documents_for_rag_config(
                tenant_id=tenant_id,
                user_id=user_id,
                rag_config_id=memory_item.rag_config_id,
            )
            if current_count < cap["effective_cap"]:
                prepared_document = (
                    await self.rag_runtime_service.prepare_document_for_embedding(
                        tenant_id=tenant_id,
                        rag_config_id=memory_item.rag_config_id,
                        document=RagDocumentCreate(
                            source=memory_item.source.value,
                            doc_type=RagUserMemoryDocumentType.USER_MEMORY_ITEM.value,
                            content=json.dumps(memory_item.data, ensure_ascii=True),
                            metadata={
                                "scope": ContextLayerScope.USER_MEMORY.value,
                                "user_id": user_id,
                                "schema_id": memory_item.schema_id,
                                "schema_version": memory_item.schema_version,
                                "policy_version_id": str(
                                    resolved_policy.policy_version_id
                                )
                                if resolved_policy.policy_version_id
                                else None,
                                "observed_at": (
                                    memory_item.observed_at.isoformat()
                                    if isinstance(memory_item.observed_at, datetime)
                                    else None
                                ),
                                "expires_at": expires_at.isoformat()
                                if expires_at
                                else None,
                            },
                        ),
                    )
                )
                result.embedded_document_id = prepared_document.id
                result.targets_applied.append(MemoryWriteTarget.USER_MEMORY_VECTOR)
                if (
                    prepared_document.embedding_status == EmbeddingStatus.COMPLETED
                    and self.embedding_job_queue is None
                ):
                    event_payload = {
                        "scope": ContextLayerScope.USER_MEMORY.value,
                        "target": MemoryWriteTarget.USER_MEMORY_VECTOR.value,
                        "schema_id": memory_item.schema_id,
                        "schema_version": memory_item.schema_version,
                        "source": memory_item.source.value,
                        "policy_version_id": str(resolved_policy.policy_version_id)
                        if resolved_policy.policy_version_id
                        else None,
                        "rag_config_id": str(memory_item.rag_config_id),
                        "document_id": str(prepared_document.id),
                    }
                    await self._append_execution_event(
                        tenant_id=tenant_id,
                        event_context=event_context,
                        event_type=ExecutionEventType.MemoryEmbedded,
                        payload=event_payload,
                    )
                elif self.embedding_job_queue is None:
                    document: RagDocument = (
                        await self.rag_runtime_service.embed_document_by_id(
                            tenant_id=tenant_id,
                            rag_config_id=memory_item.rag_config_id,
                            document_id=prepared_document.id,
                        )
                    )
                    result.embedded_document_id = document.id
                    event_payload = {
                        "scope": ContextLayerScope.USER_MEMORY.value,
                        "target": MemoryWriteTarget.USER_MEMORY_VECTOR.value,
                        "schema_id": memory_item.schema_id,
                        "schema_version": memory_item.schema_version,
                        "source": memory_item.source.value,
                        "policy_version_id": str(resolved_policy.policy_version_id)
                        if resolved_policy.policy_version_id
                        else None,
                        "rag_config_id": str(memory_item.rag_config_id),
                        "document_id": str(document.id),
                    }
                    await self._append_execution_event(
                        tenant_id=tenant_id,
                        event_context=event_context,
                        event_type=ExecutionEventType.MemoryEmbedded,
                        payload=event_payload,
                    )
                else:
                    await self.embedding_job_queue.enqueue_embedding_job(
                        payload=EmbeddingJobPayload(
                            tenant_id=tenant_id,
                            rag_config_id=memory_item.rag_config_id,
                            document_id=prepared_document.id,
                            flow_run_id=event_context.flow_run_id
                            if event_context
                            else None,
                            session_id=event_context.session_id
                            if event_context
                            else None,
                            correlation_id=event_context.correlation_id
                            if event_context
                            else None,
                            user_id=user_id,
                            policy_version_id=resolved_policy.policy_version_id,
                            schema_id=memory_item.schema_id,
                            schema_version=memory_item.schema_version,
                            expires_at=expires_at.isoformat() if expires_at else None,
                            max_attempts=settings.EMBEDDING_QUEUE_MAX_ATTEMPTS,
                        )
                    )
                    queued_payload = {
                        "scope": ContextLayerScope.USER_MEMORY.value,
                        "target": MemoryWriteTarget.USER_MEMORY_VECTOR.value,
                        "schema_id": memory_item.schema_id,
                        "schema_version": memory_item.schema_version,
                        "source": memory_item.source.value,
                        "policy_version_id": str(resolved_policy.policy_version_id)
                        if resolved_policy.policy_version_id
                        else None,
                        "rag_config_id": str(memory_item.rag_config_id),
                        "document_id": str(prepared_document.id),
                    }
                    await self._append_execution_event(
                        tenant_id=tenant_id,
                        event_context=event_context,
                        event_type=ExecutionEventType.MemoryEmbeddingQueued,
                        payload=queued_payload,
                    )

        return result

    def _find_allowed_schema(
        self,
        *,
        schema_id: str,
        policy_schemas: list[AllowedSchema],
    ) -> AllowedSchema | None:
        for allowed_schema in policy_schemas:
            if allowed_schema.schema_id == schema_id:
                return allowed_schema
        return None

    def _extract_payload_preference_key(
        self, memory_item: UserMemoryItem
    ) -> str | None:
        key = memory_item.data.get("preference_key")
        if not isinstance(key, str):
            return None
        normalized = key.strip()
        if not normalized:
            return None
        return normalized

    def _derive_preference_key(
        self,
        *,
        memory_item: UserMemoryItem,
        preference_policy: PreferenceUpdatePolicy | None,
    ) -> tuple[str | None, PreferenceKeyDerivationReason]:
        if preference_policy is None:
            return None, PreferenceKeyDerivationReason.NO_POLICY
        if preference_policy.fixed_key is not None:
            normalized_fixed_key = preference_policy.fixed_key.strip()
            if not normalized_fixed_key:
                return None, PreferenceKeyDerivationReason.NO_POLICY
            return normalized_fixed_key, PreferenceKeyDerivationReason.FIXED_KEY_USED
        payload_key = self._extract_payload_preference_key(memory_item)
        if payload_key is None:
            return None, PreferenceKeyDerivationReason.KEY_NOT_ALLOWED
        if not preference_policy.allowed_keys:
            return None, PreferenceKeyDerivationReason.KEY_NOT_ALLOWED
        if payload_key not in set(preference_policy.allowed_keys):
            return None, PreferenceKeyDerivationReason.KEY_NOT_ALLOWED
        return payload_key, PreferenceKeyDerivationReason.KEY_ALLOWED

    def _extract_preference_value(
        self,
        memory_item: UserMemoryItem,
    ) -> tuple[bool, object]:
        if "preference_value" not in memory_item.data:
            return False, None
        return True, memory_item.data.get("preference_value")

    def _source_priority_values(self) -> dict[str, int]:
        return {
            source.value: priority
            for source, priority in self.SOURCE_PRIORITY_MAP.items()
        }

    async def _emit_memory_updated_outcome(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        memory_item: UserMemoryItem,
        event_context: MemoryWriteEventContext | None,
        policy_version_id: UUID | None,
        preference_key: str | None,
        outcome: str,
        reason: str,
        new_version: int | None,
    ) -> None:
        payload = {
            "scope": ContextLayerScope.USER_MEMORY.value,
            "target": MemoryWriteTarget.USER_PREFERENCE.value,
            "schema_id": memory_item.schema_id,
            "schema_version": memory_item.schema_version,
            "source": memory_item.source.value,
            "policy_version_id": str(policy_version_id) if policy_version_id else None,
            "preference_key": preference_key,
            "outcome": outcome,
            "reason": reason,
        }
        if new_version is not None:
            payload["new_version"] = new_version
        await self._append_execution_event(
            tenant_id=tenant_id,
            event_context=event_context,
            event_type=ExecutionEventType.MemoryUpdated,
            payload=payload,
        )

    def _resolve_write_targets(
        self,
        *,
        item: UserMemoryItem,
        default_target: MemoryWriteTarget,
        policy_schemas: list,
    ) -> list[MemoryWriteTarget]:
        if not policy_schemas:
            return [default_target]
        for allowed_schema in policy_schemas:
            if allowed_schema.schema_id != item.schema_id:
                continue
            if allowed_schema.write_targets:
                return list(allowed_schema.write_targets)
            return [default_target]
        return [default_target]

    async def _append_execution_event(
        self,
        *,
        tenant_id: UUID,
        event_context: MemoryWriteEventContext | None,
        event_type: ExecutionEventType,
        payload: dict[str, object],
    ) -> None:
        if event_context is None:
            return
        if (
            event_context.session_id is None
            or event_context.flow_run_id is None
            or event_context.correlation_id is None
        ):
            return
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=event_context.session_id,
            flow_run_id=event_context.flow_run_id,
            event_type=event_type.value,
            payload=payload,
            correlation_id=event_context.correlation_id,
            causation_id=event_context.causation_id,
            node_id=event_context.node_id,
        )

    def _deep_merge(
        self,
        *,
        left: dict[str, object],
        right: dict[str, object],
    ) -> dict[str, object]:
        merged: dict[str, object] = dict(left)
        for key, value in right.items():
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(left=current, right=value)
            else:
                merged[key] = value
        return merged


class UserMemoryWriter(MemoryWriteService):
    async def append_memory_item(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        item: dict,
    ) -> None:
        with self.tracer.observe(
            as_type="span",
            name="domain.memory.writer.append_memory_item",
            input={
                "tenant_id": str(tenant_id),
                "user_id": user_id,
                "schema_id": item.get("schema_id"),
            },
        ) as handle:
            await self.write_memory_item(
                tenant_id=tenant_id,
                user_id=user_id,
                item=item,
                event_context=None,
            )
            if handle:
                handle.success(output={"status": "ok"})
