from __future__ import annotations

from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.contexts import (
    ClarificationContext,
    IntentDetectionContext,
    ResponseFormattingContext,
    SlotFillingContext,
)
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
    ):
        self.agents_repository = agents_repository
        self.tools_repository = tools_repository
        self.rag_runtime_service = rag_runtime_service
        self.tracer = tracer

    async def build_intent_context(
        self,
        agent_version_id: UUID,
        user_input: str,
        context: ExecutionContext,
    ) -> IntentDetectionContext:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.context_builder.get_agent_version_intent",
            input={"agent_version_id": str(agent_version_id)},
        ):
            agent_version = await self.agents_repository.get_agent_version(
                agent_version_id
            )
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )
        return IntentDetectionContext(
            persona=persona, user_input=user_input, context=context
        )

    async def build_slot_filling_context(
        self,
        agent_version_id: UUID,
        intent: str,
        tool_config_id: UUID,
        user_input: str,
    ) -> SlotFillingContext:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.context_builder.get_agent_version_slot",
            input={"agent_version_id": str(agent_version_id)},
        ):
            agent_version = await self.agents_repository.get_agent_version(
                agent_version_id
            )
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )

        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.context_builder.get_tool_config_slot",
            input={"tool_config_id": str(tool_config_id)},
        ):
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
        )

    async def build_response_formatting_context(
        self,
        agent_version_id: UUID,
        tool_response: dict,
        original_intent: str,
        user_input: str,
    ) -> ResponseFormattingContext:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.context_builder.get_agent_version_response",
            input={"agent_version_id": str(agent_version_id)},
        ):
            agent_version = await self.agents_repository.get_agent_version(
                agent_version_id
            )
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )
        rag_context: RagContext | None = None
        if (
            self.rag_runtime_service
            and agent_version
            and agent_version.rag_config_id
            and user_input
        ):
            rag_context = await self.rag_runtime_service.get_context(
                tenant_id=agent_version.tenant_id,
                rag_config_id=agent_version.rag_config_id,
                user_input=user_input,
            )
        return ResponseFormattingContext(
            persona=persona,
            tool_response=tool_response,
            original_intent=original_intent,
            user_input=user_input,
            rag_context=rag_context,
        )

    async def build_clarification_context(
        self,
        agent_version_id: UUID,
        intent: str,
        missing_fields: list[str],
    ) -> ClarificationContext:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.llm.context_builder.get_agent_version_clarification",
            input={"agent_version_id": str(agent_version_id)},
        ):
            agent_version = await self.agents_repository.get_agent_version(
                agent_version_id
            )
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )
        return ClarificationContext(
            persona=persona,
            intent=intent,
            missing_fields=missing_fields,
        )
