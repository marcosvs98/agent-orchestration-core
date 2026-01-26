from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.services.context_builder import ContextBuilder
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import (
    NodeType,
    PromptIntent,
    ResolvedPrompt,
)
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException
from pydantic import BaseModel


class PromptResolver:
    def __init__(
        self,
        prompt_service: PromptService,
        context_builder: ContextBuilder,
        execution_repository: ExecutionRepository,
    ):
        self.prompt_service = prompt_service
        self.context_builder = context_builder
        self.repository = execution_repository

        self._INTENT_TO_NODE_TYPE: dict[PromptIntent, NodeType] = {
            PromptIntent.INTENT_TOOL_SELECTION: NodeType.IntentToolSelectionNode,
            PromptIntent.PARAM_EXTRACTION: NodeType.ParamExtractionNode,
            PromptIntent.SLOT_FILLING: NodeType.ParamExtractionNode,
            PromptIntent.CLARIFICATION: NodeType.ClarificationNode,
            PromptIntent.RESPONSE_RENDER: NodeType.ResponseNode,
        }

        self._INTENT_TO_TASK_TYPE: dict[PromptIntent, LLMTaskType] = {
            PromptIntent.INTENT_TOOL_SELECTION: LLMTaskType.INTENT_SELECTION,
            PromptIntent.PARAM_EXTRACTION: LLMTaskType.PARAM_EXTRACTION,
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

    def _render_simple(self, template: str, context: BaseModel) -> str:
        ctx_dict = context.model_dump(mode='json')
        try:
            return template.format(ctx=ctx_dict)
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

        if intent == PromptIntent.INTENT_TOOL_SELECTION:
            context = await self.context_builder.build_intent_context(
                agent_version_id=agent_version_id,
                user_input=input_payload.get("user_input", ""),
                context=context,
            )
            return self._render_simple(template, context)

        elif intent in (PromptIntent.PARAM_EXTRACTION, PromptIntent.SLOT_FILLING):
            intent_str = input_payload.get("intent", "")
            tool_config_id_str = input_payload.get("tool_config_id")
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
                    )
                    return self._render_simple(template, context)
                except (ValueError, TypeError):
                    pass

        elif intent == PromptIntent.RESPONSE_RENDER:
            context = await self.context_builder.build_response_formatting_context(
                agent_version_id=agent_version_id,
                tool_response=input_payload.get("tool_response", {}),
                original_intent=input_payload.get("original_intent", ""),
            )
            return self._render_simple(template, context)

        return template

    def _load_schema_from_prompt(self, schema_id: str) -> Dict[str, Any] | None:
        return None

    async def resolve(
        self,
        *,
        intent: PromptIntent,
        context: ExecutionContext,
        node_id: UUID | None = None,
    ) -> ResolvedPrompt:
        node_type_enum = self._INTENT_TO_NODE_TYPE.get(intent)
        if not node_type_enum:
            raise DomainValidationException(
                message="prompt_intent_not_supported", detail=f"Intent {intent} não mapeado"
            )

        node_type = node_type_enum.value
        prompt = await self.prompt_service.get_prompt(node_type)

        if not prompt:
            raise DomainValidationException(
                message="prompt_not_found",
                detail=f"Prompt não encontrado para node_type={node_type}",
            )

        agent_version_id = await self._get_agent_version_id(node_id)

        input_payload = context.input_payload or {}
        if not input_payload and context.state:
            intent_output = context.state.get("intent_output", {})
            if isinstance(intent_output, dict):
                input_payload = {
                    "intent": intent_output.get("intent", ""),
                    "tool_config_id": intent_output.get("tool_config_id"),
                }

        rendered_prompt = prompt.template_text
        if prompt.template_text and agent_version_id:
            rendered_prompt = await self._render_prompt_with_context(
                prompt.template_text,
                agent_version_id,
                node_id,
                intent,
                input_payload,
                context
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
            prompt_version=prompt.version,
            prompt_frozen_hash=prompt.frozen_hash,
        )
