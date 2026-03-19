from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from jinja2 import DebugUndefined, Environment

from domain.ai_policy.schemas.ai import AITaskContextFlags
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.llm import LLMTaskType
from domain.llm.services.context_builder import ContextBuilder
from domain.llm.services.structured_output_schema_composer import (
    StructuredOutputSchemaComposer,
)
from domain.prompts.schemas.prompt import (
    NodeType,
    PromptIntent,
    ResolvedPrompt,
)
from domain.prompts.services.prompt_service import PromptService
from exceptions.service_exceptions import DomainValidationException


class PromptResolver:
    def __init__(
        self,
        prompt_service: PromptService,
        context_builder: ContextBuilder,
        execution_repository: ExecutionRepository,
        tracer: RuntimeTracerPort,
        structured_output_schema_composer: StructuredOutputSchemaComposer | None = None,
    ):
        self.prompt_service = prompt_service
        self.context_builder = context_builder
        self.repository = execution_repository
        self.tracer = tracer
        self.structured_output_schema_composer = structured_output_schema_composer

        self._jinja_env = Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=DebugUndefined,
        )
        self._jinja_env.filters["tojson"] = self._tojson_filter

    async def resolve(
        self,
        *,
        intent: PromptIntent,
        context: ExecutionContext,
        node_id: UUID | None = None,
        node_type: NodeType | None = None,
        prompt_id: UUID | None = None,
    ) -> ResolvedPrompt:
        with self.tracer.observe(
            as_type="agent",
            name="application.prompts.prompt_resolver.resolve",
            input={
                "intent": intent.value,
                "node_type": node_type.value if node_type else None,
                "prompt_id": str(prompt_id) if prompt_id else None,
            },
        ) as agent_span:
            resolved_node_type = self._resolve_node_type(intent, node_type)
            task_type = self._resolve_task_type(intent, resolved_node_type)
            effective_prompt_id = prompt_id
            if effective_prompt_id is None and node_id is not None:
                node = await self.repository.get_node(node_id)
                if node is not None:
                    effective_prompt_id = node.node_prompt_id

            prompt = await self._load_prompt(
                node_type=resolved_node_type,
                prompt_id=effective_prompt_id,
            )

            agent_version_id = await self._get_agent_version_id(node_id)
            task_flags = await self._get_task_flags(node_id)

            input_payload = self._build_input_payload(intent, context)

            template_ctx = await self.context_builder.build_template_context(
                agent_version_id=agent_version_id,
                task_type=task_type,
                execution_context=context,
                input_payload=input_payload,
                task_flags=task_flags,
            )

            rendered_prompt = self._render(prompt.template_text, template_ctx)
            output_schema = prompt.output_schema

            if (
                intent == PromptIntent.SLOT_FILLING
                and self.structured_output_schema_composer is not None
                and output_schema
            ):
                output_schema = await self.structured_output_schema_composer.compose_for_slot_filling(
                    execution_context=context,
                    prompt_output_schema=output_schema,
                )

            return ResolvedPrompt(
                prompt_text=self._normalize_template(rendered_prompt),
                input_schema=prompt.input_schema,
                output_schema=output_schema,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
                prompt_frozen_hash=prompt.frozen_hash,
            )

    async def _load_prompt(
        self,
        *,
        node_type: NodeType,
        prompt_id: UUID | None,
    ):
        if prompt_id:
            prompt = await self.prompt_service.get_prompt_by_id(prompt_id)
        else:
            prompt = await self.prompt_service.get_prompt(node_type.value)

        if not prompt:
            raise DomainValidationException(message="prompt_not_found")

        return prompt

    def _resolve_node_type(
        self,
        intent: PromptIntent,
        node_type: NodeType | None,
    ) -> NodeType:
        if node_type:
            return node_type

        mapping = {
            PromptIntent.INTENT_TOOL_SELECTION: NodeType.ToolSelectionNode,
            PromptIntent.SLOT_FILLING: NodeType.ParamExtractionNode,
            PromptIntent.CLARIFICATION: NodeType.ClarificationNode,
            PromptIntent.RESPONSE_RENDER: NodeType.ResponseComposer,
            PromptIntent.FALLBACK_RESPONSE: NodeType.FallbackNodeSLA,
        }

        resolved = mapping.get(intent)

        if not resolved:
            raise DomainValidationException(message="prompt_intent_not_supported")

        return resolved

    def _resolve_task_type(
        self,
        intent: PromptIntent,
        node_type: NodeType,
    ) -> LLMTaskType:
        node_map = {
            NodeType.IntentDetectionNode: LLMTaskType.INTENT_SELECTION,
            NodeType.ToolSelectionNode: LLMTaskType.INTENT_SELECTION,
            NodeType.ParamExtractionNode: LLMTaskType.SLOT_FILLING,
            NodeType.ClarificationNode: LLMTaskType.CLARIFICATION,
            NodeType.ResponseComposer: LLMTaskType.RESPONSE_RENDER,
            NodeType.FallbackNodeSLA: LLMTaskType.FALLBACK_RESPONSE,
        }

        if node_type in node_map:
            return node_map[node_type]

        intent_map = {
            PromptIntent.INTENT_TOOL_SELECTION: LLMTaskType.INTENT_SELECTION,
            PromptIntent.SLOT_FILLING: LLMTaskType.SLOT_FILLING,
            PromptIntent.CLARIFICATION: LLMTaskType.CLARIFICATION,
            PromptIntent.RESPONSE_RENDER: LLMTaskType.RESPONSE_RENDER,
            PromptIntent.FALLBACK_RESPONSE: LLMTaskType.FALLBACK_RESPONSE,
        }

        task_type = intent_map.get(intent)

        if not task_type:
            raise DomainValidationException(message="prompt_intent_not_supported")

        return task_type

    async def _get_agent_version_id(self, node_id: UUID | None) -> UUID | None:
        if not node_id:
            return None

        return await self.context_builder.agents_repository.get_agent_version_id_by_node_id(
            node_id
        )

    async def _get_task_flags(self, node_id: UUID | None) -> AITaskContextFlags | None:
        if not node_id:
            return None

        node = await self.repository.get_node(node_id)
        if not node:
            return None

        return AITaskContextFlags(
            allow_rag_tenant=bool(node.allow_rag_tenant),
            allow_user_memory=bool(node.allow_user_memory),
            allow_session_context=bool(node.allow_session_context),
            allow_memory_write=bool(node.allow_memory_write),
        )

    def _build_input_payload(
        self,
        intent: PromptIntent,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        user_input = (context.input_payload or {}).get("user_input", "")

        intent_slice = context.get_node_output(NodeType.IntentDetectionNode)
        try:
            result = intent_slice.get("result") or []
            detected_intent = result[0].get("intent_type") or ""
        except (AttributeError, IndexError, KeyError, TypeError):
            detected_intent = ""

        if intent == PromptIntent.RESPONSE_RENDER:
            tool_slice = context.get_node_output(NodeType.ToolExecutionNode)
            try:
                tool_slice.get
            except AttributeError:
                tool_slice = {}
            return {
                "tool_response": tool_slice,
                "original_intent": detected_intent or "",
                "user_input": user_input,
            }

        return {
            "intent": detected_intent or "",
            "user_input": user_input,
        }

    def _render(self, template: str, ctx: dict[str, Any]) -> str:
        compiled = self._jinja_env.from_string(template)
        return compiled.render(ctx=ctx)

    @staticmethod
    def _tojson_filter(value: Any) -> str:
        return json.dumps(value, ensure_ascii=True)

    def _normalize_template(self, template: str) -> str:
        template = re.sub(r"[ \t]+$", "", template, flags=re.MULTILINE)
        template = re.sub(r"\n\s*\n+", "\n\n", template)
        template = re.sub(r"(# .+?)\s+\n", r"\1\n", template)
        return template
