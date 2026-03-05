from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.context.ports.service import MemoryRetrievalServicePort
from domain.context.schemas.context_layers import (
    LayerUsageDecision,
    SessionContextSnapshot,
)
from domain.context.schemas.memory_retrieval import MemoryRetrievalConfig
from domain.context.services.rag_activation_service import RagActivationService
from domain.context.services.runtime_policy import RuntimeContextLayerPolicy
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.governance.schemas.rag_policy import RagActivationScope
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType
from domain.tools.repositories.tools_repository import ToolsRepository


class ContextBuilder:
    def __init__(
        self,
        agents_repository: AgentsRepository,
        tools_repository: ToolsRepository,
        tracer: RuntimeTracerPort,
        memory_retrieval_service: MemoryRetrievalServicePort | None = None,
        rag_activation_service: RagActivationService | None = None,
        runtime_context_policy: RuntimeContextLayerPolicy | None = None,
    ):
        self.agents_repository = agents_repository
        self.tools_repository = tools_repository
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

    def _first_tool_id_from_context(
        self, execution_context: ExecutionContext | None
    ) -> str | None:
        if execution_context is None:
            return None
        try:
            tool_out = execution_context.get_node_output(NodeType.ToolSelectionNode)
            result = tool_out.get("result") or []
            selected_tool = result[0].get("selected_tool") or {}
            tool_id = selected_tool.get("tool_config_id")
            if tool_id is None:
                return None
            return str(tool_id)
        except (AttributeError, IndexError, KeyError, TypeError):
            return None

    def _extract_tool_config_id(
        self,
        *,
        execution_context: ExecutionContext | None,
    ) -> UUID | None:
        if execution_context is None:
            return None
        tool_id = self._first_tool_id_from_context(execution_context)
        if not tool_id:
            return None
        try:
            return UUID(tool_id)
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
        try:
            memory_retrieval_config = runtime_policy.get("memory_retrieval") or {}
        except AttributeError:
            return MemoryRetrievalConfig()
        try:
            return MemoryRetrievalConfig.model_validate(memory_retrieval_config)
        except Exception:
            return MemoryRetrievalConfig()

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
        try:
            return runtime_policy.get("user_context_enrichment") or {}
        except AttributeError:
            return {}

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
            execution_context.get_node_output(NodeType.UserContextEnrichmentNode)
            if execution_context is not None
            else {}
        )
        if not bool(handle.get("published", False)):
            if task_type == LLMTaskType.RESPONSE_RENDER:
                default_layers = policy.get("default_layers_when_published") or {}
                try:
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
                except AttributeError:
                    return decision.model_copy(update={"allow_tenant_knowledge": True})
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
        layers = handle.get("layers") or {}
        try:
            allow_tenant_knowledge = bool(
                layers.get("allow_tenant_knowledge", decision.allow_tenant_knowledge)
            )
            allow_user_memory_structured = bool(
                layers.get(
                    "allow_user_memory_structured",
                    decision.allow_user_memory_structured,
                )
            )
            allow_user_memory_vector = bool(
                layers.get(
                    "allow_user_memory_vector", decision.allow_user_memory_vector
                )
            )
        except AttributeError:
            return decision
        return decision.model_copy(
            update={
                "allow_tenant_knowledge": allow_tenant_knowledge,
                "allow_user_memory_structured": allow_user_memory_structured,
                "allow_user_memory_vector": allow_user_memory_vector,
            }
        )

    async def build_template_context(
        self,
        *,
        agent_version_id: UUID | None,
        task_type: LLMTaskType,
        execution_context: ExecutionContext,
        input_payload: dict[str, Any],
        task_flags: AITaskContextFlags | None = None,
    ) -> dict[str, Any]:
        runtime_policy = (execution_context.metadata or {}).get("runtime_policy", {})
        user_input = input_payload.get("user_input") or ""
        state = execution_context.state or {}
        current_node_type = (execution_context.metadata or {}).get("current_node_type")
        available_tools = []
        for tool in execution_context.available_tools:
            try:
                available_tools.append(tool.model_dump(mode="json"))
            except AttributeError:
                continue

        ctx: dict[str, Any] = {
            "meta": {
                "tenant_id": str(execution_context.tenant_id),
                "user_id": execution_context.user_id,
                "session_id": str(execution_context.session_id),
                "flow_id": str(execution_context.flow_id),
                "flow_version_id": str(execution_context.flow_version_id),
                "flow_run_id": str(execution_context.flow_run_id),
                "correlation_id": str(execution_context.correlation_id),
                "current_node_id": execution_context.current_node_id,
                "current_node_run_id": str(execution_context.current_node_run_id)
                if execution_context.current_node_run_id
                else None,
                "current_node_type": current_node_type,
                "available_tools": available_tools,
            },
            "persona": {},
            "config": {
                "ai_task": task_flags.model_dump(mode="json") if task_flags else {},
                "execution_policy": runtime_policy.get("execution_policy", {}),
            },
            "input": {
                "user_input": user_input,
                "input_payload": input_payload,
            },
            "layers": {
                "tenant_knowledge": [],
                "user_memory_structured": None,
                "user_memory_vector": [],
                "session_context": None,
            },
            "state": state,
            "derived": {
                "intents": [],
                "selected_tools": [],
                "ready_operations": [],
                "pending_operations": [],
                "missing_fields": [],
            },
            "output_schema": [],
            "tool_response": {},
        }

        intent_slice = execution_context.get_node_output(NodeType.IntentDetectionNode)
        tool_slice = execution_context.get_node_output(NodeType.ToolSelectionNode)
        param_slice = execution_context.get_node_output(NodeType.ParamExtractionNode)
        tool_execution_slice = execution_context.get_node_output(
            NodeType.ToolExecutionNode
        )

        try:
            ctx["derived"]["intents"] = intent_slice.get("result") or []
        except AttributeError:
            pass
        try:
            ctx["derived"]["selected_tools"] = tool_slice.get("result") or []
        except AttributeError:
            pass

        try:
            operations = param_slice.get("result") or []
        except AttributeError:
            operations = []

        missing_fields: list[str] = []
        for operation in operations:
            try:
                operation_missing_fields = operation.get("missing_fields") or []
            except AttributeError:
                continue
            if operation_missing_fields:
                ctx["derived"]["pending_operations"].append(operation)
            else:
                ctx["derived"]["ready_operations"].append(operation)
            for field in operation_missing_fields:
                if not field:
                    continue
                try:
                    value = field.get("field")
                except AttributeError:
                    value = field
                if value:
                    missing_fields.append(str(value))
        ctx["derived"]["missing_fields"] = sorted(set(missing_fields))

        tool_response = input_payload.get("tool_response")
        if not tool_response:
            tool_response = tool_execution_slice
        try:
            ctx["tool_response"] = tool_response
        except AttributeError:
            ctx["tool_response"] = {}
        if not isinstance(ctx["tool_response"], dict):
            ctx["tool_response"] = {}

        persona = PersonaConfig()
        agent_version = None
        tenant_id = None
        tenant_rag_config_id = None
        if agent_version_id is not None:
            persona, agent_version = await self._get_persona(agent_version_id)
            ctx["persona"] = persona.model_dump(mode="json")
            tenant_rag_config_id = (
                agent_version.rag_config_id if agent_version is not None else None
            )
            if agent_version is not None:
                agent = await self.agents_repository.get_agent(agent_version.agent_id)
                if agent is not None:
                    tenant_id = agent.tenant_id

        decision = self.runtime_context_policy.decide(
            task_type=task_type,
            task_flags=task_flags,
        )
        decision = self._apply_user_context_enrichment_gating(
            decision=decision,
            execution_context=execution_context,
            task_type=task_type,
        )

        tenant_top_k_override = None
        tenant_filters_override = None
        if decision.allow_tenant_knowledge and tenant_id and tenant_rag_config_id:
            (
                tenant_allowed,
                tenant_top_k_override,
                tenant_filters_override,
            ) = await self._resolve_tenant_knowledge_activation(
                tenant_id=tenant_id,
                user_id=execution_context.user_id,
                user_input=user_input,
                task_type=task_type,
                task_flags=task_flags,
                rag_config_id=tenant_rag_config_id,
                tool_config_id=self._extract_tool_config_id(
                    execution_context=execution_context
                ),
                context_metadata=self._context_metadata(execution_context),
            )
            decision = decision.model_copy(
                update={"allow_tenant_knowledge": tenant_allowed}
            )

        rag_already_loaded = execution_context.system_context is not None
        if self.memory_retrieval_service is not None:
            if rag_already_loaded:
                if decision.allow_session_context:
                    session_context = self._build_session_snapshot(execution_context)
                    if session_context is not None:
                        ctx["layers"]["session_context"] = session_context.model_dump(
                            mode="json"
                        )
            else:
                layered_context = (
                    await self.memory_retrieval_service.get_layered_context(
                        execution_context=execution_context,
                        decision=decision,
                        task_type=task_type,
                        user_input=user_input,
                        tenant_id_for_knowledge=tenant_id,
                        tenant_rag_config_id=tenant_rag_config_id,
                        user_id_for_memory=execution_context.user_id,
                        task_flags=task_flags,
                        tool_config_id=self._extract_tool_config_id(
                            execution_context=execution_context
                        ),
                        context_metadata=self._context_metadata(execution_context),
                        config=self._memory_retrieval_config(
                            execution_context=execution_context
                        ),
                        tenant_top_k_override=tenant_top_k_override,
                        tenant_filters_override=tenant_filters_override,
                    )
                )
                session_context = layered_context.session_context
                if session_context is None and decision.allow_session_context:
                    session_context = self._build_session_snapshot(execution_context)
                if session_context is not None:
                    ctx["layers"]["session_context"] = session_context.model_dump(
                        mode="json"
                    )

                try:
                    tenant_items = (
                        layered_context.tenant_knowledge_context.rag_context.context_items
                        or []
                    )
                except AttributeError:
                    tenant_items = []
                tenant_knowledge = []
                for item in tenant_items:
                    try:
                        item_dump = item.model_dump(mode="json")
                    except AttributeError:
                        continue
                    metadata = item_dump.get("metadata") or {}
                    tenant_knowledge.append(
                        {
                            "id": item_dump.get("item_id") or item_dump.get("id"),
                            "title": metadata.get("title"),
                            "content": item_dump.get("content") or "",
                        }
                    )

                try:
                    ctx["layers"]["user_memory_structured"] = (
                        layered_context.user_memory_context.structured.model_dump(
                            mode="json"
                        )
                    )
                except AttributeError:
                    pass

                try:
                    user_vector_items = (
                        layered_context.user_memory_context.rag_context.context_items
                        or []
                    )
                except AttributeError:
                    user_vector_items = []
                user_memory_vector = []
                for item in user_vector_items:
                    try:
                        item_dump = item.model_dump(mode="json")
                    except AttributeError:
                        continue
                    user_memory_vector.append(
                        {
                            "reference": item_dump.get("item_id")
                            or item_dump.get("id"),
                            "content": item_dump.get("content") or "",
                            "score": item_dump.get("score"),
                        }
                    )

                parts: list[str] = []
                if tenant_knowledge:
                    parts.append("# Tenant Knowledge Base")
                    for item in tenant_knowledge:
                        title = item.get("title") or ""
                        content = item.get("content") or ""
                        if title:
                            parts.append(f"## {title}")
                        if content:
                            parts.append(content)

                if user_memory_vector:
                    parts.append("# User Memory")
                    for item in user_memory_vector:
                        content = item.get("content") or ""
                        if content:
                            parts.append(f"- {content}")

                if parts:
                    execution_context.system_context = "\n".join(parts)

        if current_node_type == NodeType.ParamExtractionNode:
            tool_config_id = self._extract_tool_config_id(
                execution_context=execution_context
            )
            if tool_config_id is not None:
                tool_config = await self.tools_repository.get_tool_config(
                    tool_config_id
                )
                if tool_config is not None:
                    ctx["output_schema"] = (
                        tool_config.config.get("request_schema") or []
                    )

        return ctx
