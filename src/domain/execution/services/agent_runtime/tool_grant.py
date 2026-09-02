from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.execution.schemas.agent_run import DELEGATION_TOOL_NAME, AgentRunToolGrant
from domain.execution.services.agent_runtime.definition import AgentDefinition
from domain.tools.services.agent_tool_catalog import AgentToolBinding
from exceptions.service_exceptions import DomainValidationException


class ResolvedToolGrant(BaseModel):
    """The authorization frozen onto one run.

    The runtime consults this and nothing else when a tool call arrives. A tool bound to the
    agent version but excluded here is not reachable for this execution, and the model is told
    so rather than the call silently succeeding against the wider agent catalogue.
    """

    model_config = ConfigDict(frozen=True)

    tools: list[AgentToolBinding]
    allow_agent_delegation: bool
    delegate_agent_ids: list[UUID]

    def binding_for(self, function_name: str) -> AgentToolBinding | None:
        for tool in self.tools:
            if tool.function_name == function_name:
                return tool
        return None

    def is_delegation_allowed_for(self, agent_id: UUID) -> bool:
        return self.allow_agent_delegation and agent_id in self.delegate_agent_ids

    def snapshot(self) -> dict[str, object]:
        return {
            "tools": [
                {
                    "function_name": tool.function_name,
                    "tool_id": str(tool.tool_id),
                    "tool_config_id": str(tool.tool_config_id),
                    "tool_name": tool.tool_name,
                }
                for tool in self.tools
            ],
            "allow_agent_delegation": self.allow_agent_delegation,
            "delegate_agent_ids": [str(agent_id) for agent_id in self.delegate_agent_ids],
            "delegation_tool_name": DELEGATION_TOOL_NAME if self.allow_agent_delegation else None,
        }


class ToolGrantResolver:
    def __init__(self, agents_repository: AgentsRepository) -> None:
        self.agents_repository = agents_repository

    async def resolve(
        self,
        *,
        tenant_id: UUID,
        definition: AgentDefinition,
        requested: AgentRunToolGrant,
    ) -> ResolvedToolGrant:
        available = {tool.function_name: tool for tool in definition.tools}

        if requested.allowed_tool_names is None:
            granted = list(definition.tools)
        else:
            unknown = [name for name in requested.allowed_tool_names if name not in available]
            if unknown:
                raise DomainValidationException(
                    message="tool_not_bound_to_agent_version",
                    detail={
                        "unknown_tools": unknown,
                        "available_tools": sorted(available),
                    },
                )
            granted = [available[name] for name in dict.fromkeys(requested.allowed_tool_names)]

        delegate_agent_ids: list[UUID] = []
        if requested.allow_agent_delegation:
            for delegate_agent_id in dict.fromkeys(requested.delegate_agent_ids):
                if delegate_agent_id == definition.agent_id:
                    raise DomainValidationException(message="agent_cannot_delegate_to_itself")
                delegate_agent = await self.agents_repository.get_agent(delegate_agent_id)
                if delegate_agent is None or delegate_agent.tenant_id != tenant_id:
                    raise DomainValidationException(
                        message="delegate_agent_not_found",
                        detail={"agent_id": str(delegate_agent_id)},
                    )
                delegate_agent_ids.append(delegate_agent_id)

        return ResolvedToolGrant(
            tools=granted,
            allow_agent_delegation=requested.allow_agent_delegation,
            delegate_agent_ids=delegate_agent_ids,
        )
