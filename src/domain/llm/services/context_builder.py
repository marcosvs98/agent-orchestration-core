from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.ports.service import (
    MemoryRetrievalServicePort,
    TenantKnowledgeRetrieverPort,
    UserMemoryReaderPort,
)
from domain.context.schemas.context_layers import (
    LayerUsageDecision,
    SessionContextSnapshot,
)
from domain.context.schemas.memory_retrieval import MemoryRetrievalConfig
from domain.context.services.runtime_policy import RuntimeContextLayerPolicy
from domain.context.services.rag_activation_service import RagActivationService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.governance.schemas.rag_policy import RagActivationScope
from domain.llm.schemas.contexts import (
    ClarificationContext,
    IntentDetectionContext,
    ResponseFormattingContext,
    SlotFillingContext,
)
from domain.llm.schemas.llm import LLMTaskType
from domain.rag.schemas.rag import RagContext
from domain.rag.services.rag_runtime_service import RagRuntimeService
from domain.tools.repositories.tools_repository import ToolsRepository


class ContextBuilder:
    def __init__(
        self,
        agents_repository: AgentsRepository,
        tools_repository: ToolsRepository,
        tracer: RuntimeTracerPort,
        rag_runtime_service: RagRuntimeService | None = None,
        tenant_knowledge_retriever: TenantKnowledgeRetrieverPort | None = None,
        user_memory_reader: UserMemoryReaderPort | None = None,
        memory_retrieval_service: MemoryRetrievalServicePort | None = None,
        rag_activation_service: RagActivationService | None = None,
        runtime_context_policy: RuntimeContextLayerPolicy | None = None,
    ):
        self.agents_repository = agents_repository
        self.tools_repository = tools_repository
        self.rag_runtime_service = rag_runtime_service
        self.tenant_knowledge_retriever = tenant_knowledge_retriever
        self.user_memory_reader = user_memory_reader
        self.memory_retrieval_service = memory_retrieval_service
        self.rag_activation_service = rag_activation_service
        self.runtime_context_policy = (
            runtime_context_policy or RuntimeContextLayerPolicy()
        )
        self.tracer = tracer

    def _build_session_snapshot(
        self,
        context: ExecutionContext | None,
    ) -> SessionContextSnapshot | None:
        if context is None:
            return None
        return SessionContextSnapshot(
            flow_run_id=context.flow_run_id,
            current_node_id=context.current_node_id,
            resume_to_node_id=None,
            state=context.state,
            memory=context.memory,
        )

    async def _get_persona(self, agent_version_id: UUID) -> tuple[PersonaConfig, Any]:
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            return PersonaConfig(), None
        persona = (
            PersonaConfig.model_validate(agent_version.persona_config)
            if agent_version.persona_config
            else PersonaConfig()
        )
        return persona, agent_version

    def _context_metadata(self, context: ExecutionContext | None) -> dict[str, object]:
        if context is None:
            return {}
        return {
            "flow_run_id": str(context.flow_run_id),
            "node_id": context.current_node_id,
        }

    def _extract_tool_config_id(
        self,
        *,
        execution_context: ExecutionContext | None,
    ) -> UUID | None:
        if execution_context is None:
            return None
        intent_output = (execution_context.state or {}).get("intent_output", {})
        if not isinstance(intent_output, dict):
            return None
        tool_config_id = intent_output.get("tool_config_id")
        if not isinstance(tool_config_id, str):
            return None
        try:
            return UUID(tool_config_id)
        except ValueError:
            return None

    def _memory_retrieval_config(
        self,
        *,
        execution_context: ExecutionContext | None,
    ) -> MemoryRetrievalConfig:
        if execution_context is None:
            return MemoryRetrievalConfig()
        runtime_policy = (execution_context.metadata or {}).get("runtime_policy", {})
        if not isinstance(runtime_policy, dict):
            return MemoryRetrievalConfig()
        memory_retrieval_config = runtime_policy.get("memory_retrieval")
        if not isinstance(memory_retrieval_config, dict):
            return MemoryRetrievalConfig()
        return MemoryRetrievalConfig.model_validate(memory_retrieval_config)

    async def _resolve_tenant_knowledge_activation(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None,
        user_input: str,
        task_type: LLMTaskType,
        task_flags: AITaskContextFlags | None,
        rag_config_id: UUID | None,
        tool_config_id: UUID | None,
        context_metadata: dict[str, object] | None,
    ) -> tuple[bool, int | None, dict[str, object] | None]:
        if rag_config_id is None:
            return False, None, None
        if self.rag_activation_service is None:
            return True, None, None
        activation = await self.rag_activation_service.decide(
            tenant_id=tenant_id,
            task_type=task_type,
            scope=RagActivationScope.TENANT_KNOWLEDGE,
            task_flags=task_flags,
            rag_config_id=rag_config_id,
            user_id=user_id,
            user_input=user_input,
            tool_config_id=tool_config_id,
            context_metadata=context_metadata,
        )
        if not activation.enabled:
            return False, None, None
        return (
            True,
            activation.effective_top_k,
            activation.effective_filters_override,
        )

    def _user_context_enrichment_policy(
        self, *, execution_context: ExecutionContext | None
    ) -> dict[str, object]:
        if execution_context is None:
            return {}
        runtime_policy = (execution_context.metadata or {}).get("runtime_policy", {})
        if not isinstance(runtime_policy, dict):
            return {}
        user_context_enrichment = runtime_policy.get("user_context_enrichment")
        if not isinstance(user_context_enrichment, dict):
            return {}
        return user_context_enrichment

    def _apply_user_context_enrichment_gating(
        self,
        *,
        decision: LayerUsageDecision,
        execution_context: ExecutionContext | None,
        task_type: LLMTaskType,
    ) -> LayerUsageDecision:
        policy = self._user_context_enrichment_policy(
            execution_context=execution_context
        )
        if not bool(policy.get("gating", False)):
            return decision
        handle = (
            (execution_context.state or {}).get("user_context_enrichment", {})
            if execution_context is not None
            else {}
        )
        if not isinstance(handle, dict):
            handle = {}
        if not bool(handle.get("published", False)):
            if task_type == LLMTaskType.RESPONSE_RENDER:
                default_layers = policy.get("default_layers_when_published")
                if isinstance(default_layers, dict):
                    return decision.model_copy(
                        update={
                            "allow_tenant_knowledge": bool(
                                default_layers.get(
                                    "allow_tenant_knowledge",
                                    decision.allow_tenant_knowledge,
                                )
                            ),
                            "allow_user_memory_structured": bool(
                                default_layers.get(
                                    "allow_user_memory_structured",
                                    decision.allow_user_memory_structured,
                                )
                            ),
                            "allow_user_memory_vector": bool(
                                default_layers.get(
                                    "allow_user_memory_vector",
                                    decision.allow_user_memory_vector,
                                )
                            ),
                        }
                    )
                return decision.model_copy(
                    update={"allow_tenant_knowledge": True}
                )
            with self.tracer.observe(
                as_type="event",
                name="domain.context.user_context_enrichment.gated_block",
                input={
                    "task_type": task_type.value,
                    "published": False,
                    "allow_tenant_knowledge": False,
                    "allow_user_memory_structured": False,
                    "allow_user_memory_vector": False,
                },
            ):
                pass
            return decision.model_copy(
                update={
                    "allow_tenant_knowledge": False,
                    "allow_user_memory_structured": False,
                    "allow_user_memory_vector": False,
                }
            )
        layers = handle.get("layers")
        if not isinstance(layers, dict):
            return decision
        return decision.model_copy(
            update={
                "allow_tenant_knowledge": bool(
                    layers.get(
                        "allow_tenant_knowledge", decision.allow_tenant_knowledge
                    )
                ),
                "allow_user_memory_structured": bool(
                    layers.get(
                        "allow_user_memory_structured",
                        decision.allow_user_memory_structured,
                    )
                ),
                "allow_user_memory_vector": bool(
                    layers.get(
                        "allow_user_memory_vector",
                        decision.allow_user_memory_vector,
                    )
                ),
            }
        )

    async def build_intent_context(
        self,
        agent_version_id: UUID,
        user_input: str,
        context: ExecutionContext,
        task_flags: AITaskContextFlags | None = None,
    ) -> IntentDetectionContext:
        persona, agent_version = await self._get_persona(agent_version_id)
        decision = self.runtime_context_policy.decide(
            task_type=LLMTaskType.INTENT_SELECTION,
            task_flags=task_flags,
        )
        decision = self._apply_user_context_enrichment_gating(
            decision=decision,
            execution_context=context,
            task_type=LLMTaskType.INTENT_SELECTION,
        )
        tenant_knowledge_context = None
        user_memory_context = None
        session_context = (
            self._build_session_snapshot(context)
            if decision.allow_session_context
            else None
        )
        tenant_id: UUID | None = None
        if agent_version:
            agent = await self.agents_repository.get_agent(agent_version.agent_id)
            tenant_id = agent.tenant_id if agent else None
        tenant_allowed = decision.allow_tenant_knowledge
        tenant_top_k_override = None
        tenant_filters_override = None
        if (
            tenant_allowed
            and tenant_id
            and agent_version
            and agent_version.rag_config_id
        ):
            (
                tenant_allowed,
                tenant_top_k_override,
                tenant_filters_override,
            ) = await self._resolve_tenant_knowledge_activation(
                tenant_id=tenant_id,
                user_id=context.user_id,
                user_input=user_input,
                task_type=LLMTaskType.INTENT_SELECTION,
                task_flags=task_flags,
                rag_config_id=agent_version.rag_config_id,
                tool_config_id=None,
                context_metadata=self._context_metadata(context),
            )
            decision = decision.model_copy(
                update={"allow_tenant_knowledge": tenant_allowed}
            )
        if self.memory_retrieval_service is not None:
            layered_context = await self.memory_retrieval_service.get_layered_context(
                execution_context=context,
                decision=decision,
                task_type=LLMTaskType.INTENT_SELECTION,
                user_input=user_input,
                tenant_id_for_knowledge=tenant_id,
                tenant_rag_config_id=agent_version.rag_config_id
                if agent_version
                else None,
                user_id_for_memory=context.user_id,
                task_flags=task_flags,
                tool_config_id=None,
                context_metadata=self._context_metadata(context),
                config=self._memory_retrieval_config(execution_context=context),
                tenant_top_k_override=tenant_top_k_override,
                tenant_filters_override=tenant_filters_override,
            )
            session_context = layered_context.session_context
            tenant_knowledge_context = layered_context.tenant_knowledge_context
            user_memory_context = layered_context.user_memory_context
        return IntentDetectionContext(
            persona=persona,
            user_input=user_input,
            context=context,
            session_context=session_context,
            user_memory_context=user_memory_context,
            tenant_knowledge_context=tenant_knowledge_context,
        )

    async def build_slot_filling_context(
        self,
        agent_version_id: UUID,
        intent: str,
        tool_config_id: UUID,
        user_input: str,
        execution_context: ExecutionContext | None = None,
        task_flags: AITaskContextFlags | None = None,
    ) -> SlotFillingContext:
        persona, agent_version = await self._get_persona(agent_version_id)
        decision = self.runtime_context_policy.decide(
            task_type=LLMTaskType.SLOT_FILLING,
            task_flags=task_flags,
        )
        decision = self._apply_user_context_enrichment_gating(
            decision=decision,
            execution_context=execution_context,
            task_type=LLMTaskType.SLOT_FILLING,
        )
        tenant_knowledge_context = None
        user_memory_context = None
        session_context = (
            self._build_session_snapshot(execution_context)
            if decision.allow_session_context
            else None
        )
        tenant_id: UUID | None = None
        if agent_version:
            agent = await self.agents_repository.get_agent(agent_version.agent_id)
            tenant_id = agent.tenant_id if agent else None
        tenant_allowed = decision.allow_tenant_knowledge
        tenant_top_k_override = None
        tenant_filters_override = None
        if (
            tenant_allowed
            and tenant_id
            and agent_version
            and agent_version.rag_config_id
        ):
            (
                tenant_allowed,
                tenant_top_k_override,
                tenant_filters_override,
            ) = await self._resolve_tenant_knowledge_activation(
                tenant_id=tenant_id,
                user_id=execution_context.user_id if execution_context else None,
                user_input=user_input,
                task_type=LLMTaskType.SLOT_FILLING,
                task_flags=task_flags,
                rag_config_id=agent_version.rag_config_id,
                tool_config_id=tool_config_id,
                context_metadata=self._context_metadata(execution_context),
            )
            decision = decision.model_copy(
                update={"allow_tenant_knowledge": tenant_allowed}
            )
        if self.memory_retrieval_service is not None:
            layered_context = await self.memory_retrieval_service.get_layered_context(
                execution_context=execution_context,
                decision=decision,
                task_type=LLMTaskType.SLOT_FILLING,
                user_input=user_input,
                tenant_id_for_knowledge=tenant_id,
                tenant_rag_config_id=agent_version.rag_config_id
                if agent_version
                else None,
                user_id_for_memory=execution_context.user_id
                if execution_context
                else None,
                task_flags=task_flags,
                tool_config_id=tool_config_id,
                context_metadata=self._context_metadata(execution_context),
                config=self._memory_retrieval_config(
                    execution_context=execution_context
                ),
                tenant_top_k_override=tenant_top_k_override,
                tenant_filters_override=tenant_filters_override,
            )
            session_context = layered_context.session_context
            tenant_knowledge_context = layered_context.tenant_knowledge_context
            user_memory_context = layered_context.user_memory_context

        tool_config = await self.tools_repository.get_tool_config(tool_config_id)
        if tool_config is None:
            request_schema = {}
        else:
            request_schema = tool_config.config.get("request_schema", {})

        return SlotFillingContext(
            persona=persona,
            intent=intent,
            user_input=user_input,
            tool_config_id=tool_config_id,
            request_schema=request_schema,
            session_context=session_context,
            user_memory_context=user_memory_context,
            tenant_knowledge_context=tenant_knowledge_context,
        )

    async def build_response_formatting_context(
        self,
        agent_version_id: UUID,
        tool_response: dict,
        original_intent: str,
        user_input: str,
        user_id: str | None = None,
        execution_context: ExecutionContext | None = None,
        task_flags: AITaskContextFlags | None = None,
    ) -> ResponseFormattingContext:
        persona, agent_version = await self._get_persona(agent_version_id)
        decision = self.runtime_context_policy.decide(
            task_type=LLMTaskType.RESPONSE_RENDER,
            task_flags=task_flags,
        )
        decision = self._apply_user_context_enrichment_gating(
            decision=decision,
            execution_context=execution_context,
            task_type=LLMTaskType.RESPONSE_RENDER,
        )
        user_memory_context = None
        rag_context: RagContext | None = None
        tenant_knowledge_context = None
        session_context = (
            self._build_session_snapshot(execution_context)
            if decision.allow_session_context
            else None
        )
        tenant_id: UUID | None = None
        if agent_version:
            agent = await self.agents_repository.get_agent(agent_version.agent_id)
            tenant_id = agent.tenant_id if agent else None
        resolved_tool_config_id = self._extract_tool_config_id(
            execution_context=execution_context
        )
        tenant_allowed = decision.allow_tenant_knowledge
        tenant_top_k_override = None
        tenant_filters_override = None
        if (
            tenant_allowed
            and tenant_id
            and agent_version
            and agent_version.rag_config_id
        ):
            (
                tenant_allowed,
                tenant_top_k_override,
                tenant_filters_override,
            ) = await self._resolve_tenant_knowledge_activation(
                tenant_id=tenant_id,
                user_id=user_id,
                user_input=user_input,
                task_type=LLMTaskType.RESPONSE_RENDER,
                task_flags=task_flags,
                rag_config_id=agent_version.rag_config_id,
                tool_config_id=resolved_tool_config_id,
                context_metadata=self._context_metadata(execution_context),
            )
            decision = decision.model_copy(
                update={"allow_tenant_knowledge": tenant_allowed}
            )
        if self.memory_retrieval_service is not None:
            layered_context = await self.memory_retrieval_service.get_layered_context(
                execution_context=execution_context,
                decision=decision,
                task_type=LLMTaskType.RESPONSE_RENDER,
                user_input=user_input,
                tenant_id_for_knowledge=tenant_id,
                tenant_rag_config_id=agent_version.rag_config_id
                if agent_version
                else None,
                user_id_for_memory=user_id,
                task_flags=task_flags,
                tool_config_id=resolved_tool_config_id,
                context_metadata=self._context_metadata(execution_context),
                config=self._memory_retrieval_config(
                    execution_context=execution_context
                ),
                tenant_top_k_override=tenant_top_k_override,
                tenant_filters_override=tenant_filters_override,
            )
            session_context = layered_context.session_context
            tenant_knowledge_context = layered_context.tenant_knowledge_context
            user_memory_context = layered_context.user_memory_context
            rag_context = (
                tenant_knowledge_context.rag_context
                if tenant_knowledge_context is not None
                else None
            )
        return ResponseFormattingContext(
            persona=persona,
            tool_response=tool_response,
            original_intent=original_intent,
            user_input=user_input,
            rag_context=rag_context,
            session_context=session_context,
            user_memory_context=user_memory_context,
            tenant_knowledge_context=tenant_knowledge_context,
        )

    async def build_clarification_context(
        self,
        agent_version_id: UUID,
        intent: str,
        missing_fields: list[str],
        execution_context: ExecutionContext | None = None,
        task_flags: AITaskContextFlags | None = None,
    ) -> ClarificationContext:
        persona, _ = await self._get_persona(agent_version_id)
        decision = self.runtime_context_policy.decide(
            task_type=LLMTaskType.CLARIFICATION,
            task_flags=task_flags,
        )
        return ClarificationContext(
            persona=persona,
            intent=intent,
            missing_fields=missing_fields,
            session_context=(
                self._build_session_snapshot(execution_context)
                if decision.allow_session_context
                else None
            ),
        )
