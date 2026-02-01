from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.llm.schemas.contexts import (
    ClarificationContext,
    IntentDetectionContext,
    ResponseFormattingContext,
    SlotFillingContext,
)
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.tools.repositories.tools_repository import ToolsRepository


class ContextBuilder:
    def __init__(
        self,
        agents_repository: AgentsRepository,
        tools_repository: ToolsRepository,
    ):
        self.agents_repository = agents_repository
        self.tools_repository = tools_repository

    async def build_intent_context(
        self,
        agent_version_id: UUID,
        user_input: str,
        context: ExecutionContext,
    ) -> IntentDetectionContext:
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
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
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )

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
    ) -> ResponseFormattingContext:
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            persona = PersonaConfig()
        else:
            persona = (
                PersonaConfig.model_validate(agent_version.persona_config)
                if agent_version.persona_config
                else PersonaConfig()
            )
        return ResponseFormattingContext(
            persona=persona,
            tool_response=tool_response,
            original_intent=original_intent,
        )

    async def build_clarification_context(
        self,
        agent_version_id: UUID,
        intent: str,
        missing_fields: list[str],
    ) -> ClarificationContext:
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
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
