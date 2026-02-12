from __future__ import annotations

import json
from typing import Any, Dict
from uuid import UUID

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.context.schemas.context_layers import UserMemoryContext
from domain.llm.services.context_builder import ContextBuilder
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import (
    NodeType,
    PromptIntent,
    ResolvedPrompt,
)
from domain.llm.schemas.contexts import IntentDetectionContext
from domain.rag.schemas.rag import RagGenerationContract
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException
from pydantic import BaseModel


class PromptResolver:
    def __init__(
        self,
        prompt_service: PromptService,
        context_builder: ContextBuilder,
        execution_repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
    ):
        self.prompt_service = prompt_service
        self.context_builder = context_builder
        self.repository = execution_repository
        self.tracer = tracer
        self._INTENT_TO_NODE_TYPE: dict[PromptIntent, NodeType] = {
            PromptIntent.INTENT_TOOL_SELECTION: NodeType.IntentToolSelectionNode,
            PromptIntent.SLOT_FILLING: NodeType.ParamExtractionNode,
            PromptIntent.CLARIFICATION: NodeType.ClarificationNode,
            PromptIntent.RESPONSE_RENDER: NodeType.ResponseNode,
        }

        self._INTENT_TO_TASK_TYPE: dict[PromptIntent, LLMTaskType] = {
            PromptIntent.INTENT_TOOL_SELECTION: LLMTaskType.INTENT_SELECTION,
            PromptIntent.SLOT_FILLING: LLMTaskType.SLOT_FILLING,
            PromptIntent.CLARIFICATION: LLMTaskType.CLARIFICATION,
            PromptIntent.RESPONSE_RENDER: LLMTaskType.RESPONSE_RENDER,
        }

    async def _get_agent_version_id(self, node_id: UUID | None) -> UUID | None:
        if not node_id:
            return None

        return await self.context_builder.agents_repository.get_agent_version_id_by_node_id(
            node_id
        )

    async def _get_task_flags(
        self, node_id: UUID | None
    ) -> tuple[AITaskContextFlags | None, dict[str, Any]]:
        if not node_id:
            return None, {}
        node = await self.repository.get_node(node_id)
        if node is None or node.ai_task_id is None:
            return None, {}
        ai_task = await self.repository.get_ai_task(node.ai_task_id)
        if ai_task is None:
            return None, {}
        flags = AITaskContextFlags(
            allow_rag_tenant=bool(ai_task.allow_rag_tenant),
            allow_user_memory=bool(ai_task.allow_user_memory),
            allow_session_context=bool(ai_task.allow_session_context),
            allow_memory_write=bool(ai_task.allow_memory_write),
        )
        metadata = {
            "ai_task_id": str(ai_task.ai_task_id),
            "ai_task_name": ai_task.name,
            "allow_rag_tenant": flags.allow_rag_tenant,
            "allow_user_memory": flags.allow_user_memory,
            "allow_session_context": flags.allow_session_context,
            "allow_memory_write": flags.allow_memory_write,
        }
        return flags, metadata

    def _render_simple(self, template: str, context: BaseModel) -> str:
        ctx: dict = context.model_dump(mode="json")
        try:
            return template.format(ctx=ctx)
        except (KeyError, ValueError):
            return template

    async def _render_prompt_with_context(
        self,
        template: str,
        agent_version_id: UUID | None,
        node_id: UUID | None,
        intent: PromptIntent,
        input_payload: Dict[str, Any],
        context: ExecutionContext,
    ) -> str:
        if not agent_version_id:
            return template

        task_type = self._INTENT_TO_TASK_TYPE.get(intent)
        if not task_type:
            return template
        task_flags, flags_metadata = await self._get_task_flags(node_id)
        with self.tracer.observe(
            as_type="event",
            name="application.prompts.prompt_resolver.context_flags",
            input={
                "intent": intent.value,
                "node_id": str(node_id) if node_id else None,
                "task_type": task_type.value,
                **flags_metadata,
            },
        ): # Todo: Fix it - Because All observations needs to have a context and output. Only input and pass don't seems a good idea !
            pass

        if intent == PromptIntent.INTENT_TOOL_SELECTION:
            context: IntentDetectionContext = (
                await self.context_builder.build_intent_context(
                    agent_version_id=agent_version_id,
                    user_input=input_payload.get("user_input", ""),
                    context=context,
                    task_flags=task_flags,
                )
            )
            return self._render_simple(template, context)

        elif intent == PromptIntent.SLOT_FILLING:
            intent_output = (context.state or {}).get("intent_output", {})
            intent_str = intent_output.get("intent", "")
            tool_config_id_str = intent_output.get("tool_config_id")
            user_input = input_payload.get("user_input", "")
            if tool_config_id_str:
                try:
                    tool_config_id = (
                        UUID(tool_config_id_str)
                        if isinstance(tool_config_id_str, str)
                        else tool_config_id_str
                    )
                    context = await self.context_builder.build_slot_filling_context(
                        agent_version_id=agent_version_id,
                        intent=intent_str,
                        tool_config_id=tool_config_id,
                        user_input=user_input,
                        execution_context=context,
                        task_flags=task_flags,
                    )
                    return self._render_simple(template, context)
                except (ValueError, TypeError):
                    pass

        elif intent == PromptIntent.CLARIFICATION:
            missing_fields = (
                (context.state or {}).get("missing_fields", []) if context else []
            )
            if isinstance(missing_fields, str):
                missing_fields = [missing_fields]
            if not isinstance(missing_fields, list):
                missing_fields = []
            intent_value = ""
            intent_output = (context.state or {}).get("intent_output", {})
            if isinstance(intent_output, dict):
                intent_value = intent_output.get("intent", "") or ""
            context = await self.context_builder.build_clarification_context(
                agent_version_id=agent_version_id,
                intent=intent_value,
                missing_fields=missing_fields,
                execution_context=context,
                task_flags=task_flags,
            )
            return self._render_simple(template, context)

        elif intent == PromptIntent.RESPONSE_RENDER:
            context = await self.context_builder.build_response_formatting_context(
                agent_version_id=agent_version_id,
                tool_response=input_payload.get("tool_response", {}),
                original_intent=input_payload.get("original_intent", ""),
                user_input=input_payload.get("user_input", ""),
                user_id=context.user_id,
                execution_context=context,
                task_flags=task_flags,
            )
            rendered = self._render_simple(template, context)
            tenant_knowledge_context = (
                context.tenant_knowledge_context.rag_context
                if context.tenant_knowledge_context
                else context.rag_context
            )
            if tenant_knowledge_context:
                rendered = self._append_rag_contract(
                    rendered, tenant_knowledge_context, context.user_input
                )
            if context.user_memory_context:
                rendered = self._append_user_memory_contract(
                    rendered, context.user_memory_context
                )
            return rendered

        return template

    def _format_no_context_instruction(self, behavior: str) -> str:
        if behavior == "ASK_CLARIFICATION":
            return (
                "If the context is insufficient, ask a concise clarification question "
                "and do not answer."
            )
        return (
            'If the context is insufficient, answer with: "I do not have enough '
            'information to answer this question."'
        )

    def _append_rag_contract(
        self, prompt: str, rag_context: Any, user_input: str
    ) -> str:
        context_items = rag_context.context_items if rag_context else []
        context_payload = [
            {
                "content": item.content,
                "score": item.score,
                "metadata": item.metadata or {},
            }
            for item in context_items
        ]
        generation_contract = (
            rag_context.generation_contract
            if rag_context and rag_context.generation_contract
            else RagGenerationContract()
        )
        retrieval_status = {
            "eligible": bool(getattr(rag_context, "eligible", False)),
            "reason": getattr(rag_context, "reason", "UNKNOWN"),
        }
        extrapolation_instruction = (
            "You may extrapolate beyond the retrieved context, but explicitly label "
            "assumptions."
            if generation_contract.allow_extrapolation
            else "Do not extrapolate beyond the retrieved context."
        )
        contract = (
            "\n\n## Retrieved Context\n"
            f"{json.dumps(context_payload, ensure_ascii=True)}\n\n"
            "## Retrieval Status\n"
            f"{json.dumps(retrieval_status, ensure_ascii=True)}\n\n"
            "## Contract\n"
            f"{extrapolation_instruction} "
            f"{self._format_no_context_instruction(generation_contract.no_context_behavior)}"
        )
        if user_input:
            contract = (
                contract
                + "\n\n"
                + "## User Input\n"
                + json.dumps({"user_input": user_input}, ensure_ascii=True)
            )
        return prompt + contract

    def _append_user_memory_contract(
        self, prompt: str, user_memory_context: UserMemoryContext
    ) -> str:
        structured_payload = {
            "preferences": user_memory_context.structured.preferences,
            "profile": user_memory_context.structured.profile,
        }
        payload = (
            user_memory_context.rag_context.context_items
            if user_memory_context.rag_context
            else []
        )
        memory_items = [
            {
                "document_id": str(item.document_id),
                "chunk_id": str(item.chunk_id),
                "content": item.content,
                "score": item.score,
                "metadata": item.metadata or {},
            }
            for item in payload
        ]
        return (
            prompt
            + "\n\n## User Memory Structured\n"
            + json.dumps(structured_payload, ensure_ascii=True)
            + "\n\n## User Memory Retrieved\n"
            + json.dumps(memory_items, ensure_ascii=True)
        )

    def _load_schema_from_prompt(self, schema_id: str) -> Dict[str, Any] | None:
        return None

    async def resolve(
        self,
        *,
        intent: PromptIntent,
        context: ExecutionContext,
        node_id: UUID | None = None,
    ) -> ResolvedPrompt:
        with self.tracer.observe(
            as_type="agent",
            name="application.prompts.prompt_resolver.resolve",
            input={"intent": intent.value},
        ):
            node_type_enum = self._INTENT_TO_NODE_TYPE.get(intent)
            if not node_type_enum:
                raise DomainValidationException(
                    message="prompt_intent_not_supported",
                    detail=f"Intent {intent} is not supported",
                )

            node_type = node_type_enum.value
            prompt = await self.prompt_service.get_prompt(node_type)

            if not prompt:
                raise DomainValidationException(
                    message="prompt_not_found",
                    detail=f"Prompt not found for node_type={node_type}",
                )

            agent_version_id = await self._get_agent_version_id(node_id)

            input_payload = context.input_payload or {}
            if context.state:
                intent_output = context.state.get("intent_output", {})
                if isinstance(intent_output, dict):
                    user_input = (context.input_payload or {}).get("user_input", "")
                    input_payload = {
                        "intent": intent_output.get("intent", ""),
                        "tool_config_id": intent_output.get("tool_config_id"),
                        "user_input": user_input,
                    }

            if intent == PromptIntent.RESPONSE_RENDER:
                intent_output = (context.state or {}).get("intent_output", {})
                original_intent = (
                    intent_output.get("intent", "")
                    if isinstance(intent_output, dict)
                    else ""
                )
                tool_response = (
                    context.node_output.get("output", {}) if context.node_output else {}
                )
                input_payload = {
                    "tool_response": tool_response,
                    "original_intent": original_intent,
                    "user_input": (context.input_payload or {}).get("user_input", ""),
                }

            rendered_prompt = prompt.template_text
            if prompt.template_text and agent_version_id:
                rendered_prompt = await self._render_prompt_with_context(
                    prompt.template_text,
                    agent_version_id,
                    node_id,
                    intent,
                    input_payload,
                    context,
                )

            input_schema = None
            if prompt.input_schema_id:
                schema_data = self._load_schema_from_prompt(prompt.input_schema_id)
                if schema_data:
                    input_schema = schema_data

            output_schema = None
            if prompt.output_schema_id:
                schema_data = self._load_schema_from_prompt(prompt.output_schema_id)
                if schema_data:
                    output_schema = schema_data

            return ResolvedPrompt(
                prompt_text=rendered_prompt,
                input_schema=input_schema,
                output_schema=output_schema,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
                prompt_frozen_hash=prompt.frozen_hash,
            )
