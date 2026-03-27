from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.governance.schemas.rag_policy import (
    RagActivationDecision,
    RagActivationDecisionReason,
    RagActivationScope,
)
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.llm.schemas.llm import LLMTaskType
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfigOptions
from domain.tools.repositories.tools_repository import ToolsRepository


class RagInputKind(StrEnum):
    EMPTY = "EMPTY"
    SHORT = "SHORT"
    STRUCTURED = "STRUCTURED"
    TEXT = "TEXT"


class RagActivationService:
    def __init__(
        self,
        repository: ExecutionRepository,
        rag_repository: RagRepository,
        tools_repository: ToolsRepository,
        rag_policy_service: RagPolicyService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.repository = repository
        self.rag_repository = rag_repository
        self.tools_repository = tools_repository
        self.rag_policy_service = rag_policy_service
        self.tracer = tracer

    async def decide(
        self,
        *,
        tenant_id: UUID,
        task_type: LLMTaskType,
        scope: RagActivationScope,
        task_flags: AITaskContextFlags | None,
        rag_config_id: UUID | None,
        user_id: str | None = None,
        user_input: str | None = None,
        tool_config_id: UUID | None = None,
        intent_metadata: dict[str, object] | None = None,
        context_metadata: dict[str, object] | None = None,
    ) -> RagActivationDecision:
        input_len = len(user_input.strip()) if isinstance(user_input, str) else 0
        input_kind = self._classify_input(user_input=user_input)
        structural_allowed = self._structural_gate(scope=scope, task_flags=task_flags)
        if not structural_allowed:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.STRUCTURAL_DENY,
            )
            return decision

        resolved_policy, scope_policy = await self.rag_policy_service.scope_policy(
            tenant_id=tenant_id,
            task_type=task_type,
            scope=scope,
        )
        if resolved_policy.definition is None:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.POLICY_MISSING,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        if scope_policy is None or not bool(scope_policy.enabled):
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.POLICY_DENY,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        if scope_policy.allowed_tool_config_ids:
            if tool_config_id is None or tool_config_id not in set(
                scope_policy.allowed_tool_config_ids
            ):
                decision = RagActivationDecision(
                    enabled=False,
                    scope=scope,
                    reason=RagActivationDecisionReason.POLICY_DENY,
                    policy_version_id=resolved_policy.policy_version_id,
                )
                return decision

        explicit_tool_allow, filters_override = await self._tool_scope_metadata(
            scope=scope,
            tool_config_id=tool_config_id,
        )
        if explicit_tool_allow is False:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.TOOL_CONFIG_EXPLICIT_DENY,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        if rag_config_id is None:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.RAG_CONFIG_MISSING,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        rag_config = await self.rag_repository.get_rag_config(rag_config_id)
        if rag_config is None:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.RAG_CONFIG_NOT_FOUND,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        if rag_config.tenant_id != tenant_id:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.RAG_CONFIG_TENANT_MISMATCH,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        definition = resolved_policy.definition
        if (
            definition.require_published_rag_config
            and str(rag_config.status) != VersionStatus.PUBLISHED.value
        ):
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.RAG_CONFIG_NOT_PUBLISHED,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        if scope == RagActivationScope.USER_MEMORY_VECTOR and not user_id:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=RagActivationDecisionReason.USER_ID_MISSING,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        heuristic_reason = self._heuristic_reason(
            scope=scope,
            user_input=user_input,
            min_chars_by_scope=resolved_policy.definition.min_query_chars_by_scope,
            allow_structured_input=resolved_policy.definition.allow_structured_input,
        )
        if heuristic_reason is not None:
            decision = RagActivationDecision(
                enabled=False,
                scope=scope,
                reason=heuristic_reason,
                policy_version_id=resolved_policy.policy_version_id,
            )
            return decision

        rag_options = RagConfigOptions.model_validate(rag_config.options or {})
        effective_top_k = self.rag_policy_service.cap_top_k(
            top_k=int(rag_options.retrieval.top_k),
            resolved_policy=resolved_policy,
        )
        reason = (
            RagActivationDecisionReason.TOOL_CONFIG_EXPLICIT_ALLOW
            if explicit_tool_allow is True
            else RagActivationDecisionReason.POLICY_DEFAULT_ALLOW
        )
        decision = RagActivationDecision(
            enabled=True,
            scope=scope,
            reason=reason,
            policy_version_id=resolved_policy.policy_version_id,
            effective_top_k=effective_top_k,
            effective_filters_override=self._effective_filters_override(
                scope=scope,
                user_id=user_id,
                filters_override=filters_override,
            ),
        )
        return decision

    def _structural_gate(
        self,
        *,
        scope: RagActivationScope,
        task_flags: AITaskContextFlags | None,
    ) -> bool:
        if task_flags is None:
            return False
        if scope == RagActivationScope.TENANT_KNOWLEDGE:
            return bool(task_flags.allow_rag_tenant)
        return bool(
            task_flags.allow_user_memory_structured
            or task_flags.allow_user_memory_vector
        )

    async def _tool_scope_metadata(
        self,
        *,
        scope: RagActivationScope,
        tool_config_id: UUID | None,
    ) -> tuple[bool | None, dict[str, object] | None]:
        if tool_config_id is None:
            return None, None
        tool_config = await self.tools_repository.get_tool_config(tool_config_id)
        if tool_config is None:
            return None, None
        config = tool_config.config or {}
        rag_activation = config.get("rag_activation")
        if not isinstance(rag_activation, dict):
            return None, None
        key = (
            "tenant_knowledge"
            if scope == RagActivationScope.TENANT_KNOWLEDGE
            else "user_memory_vector"
        )
        scope_cfg = rag_activation.get(key)
        if not isinstance(scope_cfg, dict):
            return None, None
        enabled = scope_cfg.get("enabled")
        filters_override = scope_cfg.get("filters_override")
        normalized_filters = (
            filters_override if isinstance(filters_override, dict) else None
        )
        if isinstance(enabled, bool):
            return enabled, normalized_filters
        return None, normalized_filters

    def _effective_filters_override(
        self,
        *,
        scope: RagActivationScope,
        user_id: str | None,
        filters_override: dict[str, object] | None,
    ) -> dict[str, object]:
        allowed_keys = {"tags", "namespace", "doc_type"}
        scoped_override = (
            {
                key: value
                for key, value in filters_override.items()
                if key in allowed_keys
            }
            if isinstance(filters_override, dict)
            else {}
        )
        if scope == RagActivationScope.TENANT_KNOWLEDGE:
            return {
                **scoped_override,
                "scope": "TENANT_KNOWLEDGE",
            }
        return {
            **scoped_override,
            "scope": "USER_MEMORY",
            "user_id": user_id,
        }

    @staticmethod
    def _classify_input(*, user_input: str | None) -> RagInputKind:
        if user_input is None:
            return RagInputKind.EMPTY
        normalized = user_input.strip()
        if not normalized:
            return RagInputKind.EMPTY
        if normalized.startswith("{") or normalized.startswith("["):
            return RagInputKind.STRUCTURED
        return RagInputKind.TEXT

    @staticmethod
    def _heuristic_reason(
        *,
        scope: RagActivationScope,
        user_input: str | None,
        min_chars_by_scope: dict[RagActivationScope, int],
        allow_structured_input: bool,
    ) -> RagActivationDecisionReason | None:
        normalized = (user_input or "").strip()
        if not normalized:
            return RagActivationDecisionReason.INPUT_EMPTY
        min_chars = int(min_chars_by_scope.get(scope, 8))
        if len(normalized) < min_chars:
            return RagActivationDecisionReason.INPUT_TOO_SHORT
        if not allow_structured_input and (
            normalized.startswith("{") or normalized.startswith("[")
        ):
            return RagActivationDecisionReason.INPUT_STRUCTURED
        return None
