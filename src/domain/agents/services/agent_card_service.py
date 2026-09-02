from __future__ import annotations

from uuid import UUID

from domain.agents.schemas.a2a import (
    A2AAgentCapabilities,
    A2AAgentCard,
    A2AAgentSkill,
    A2A_PROTOCOL_VERSION,
)
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.tools.repositories.tools_repository import ToolsRepository
from exceptions.service_exceptions import NotFoundServiceException


class AgentCardService:
    """Publishes an AOC agent as an A2A Agent Card.

    Skills are derived from the tools the agent's active version is bound to, so the card
    advertises exactly what that version can do rather than a hand-maintained list that drifts
    from the published configuration.
    """

    def __init__(
        self,
        agents_repository: AgentsRepository,
        tools_repository: ToolsRepository,
        public_base_url: str,
    ) -> None:
        self.agents_repository = agents_repository
        self.tools_repository = tools_repository
        self.public_base_url = public_base_url.rstrip("/")

    def _rpc_url(self, agent_id: UUID) -> str:
        return f"{self.public_base_url}/core/v1/a2a/agents/{agent_id}"

    async def build_agent_card(self, *, tenant_id: UUID, agent_id: UUID) -> A2AAgentCard:
        agent = await self.agents_repository.get_agent(agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        active_version_id = await self.agents_repository.get_active_agent_version_id(agent_id)
        if active_version_id is None:
            raise NotFoundServiceException(message="agent_active_version_not_found")
        agent_version = await self.agents_repository.get_agent_version(active_version_id)
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")

        bindings = await self.tools_repository.list_tool_bindings_by_agent_version_id(
            tenant_id=tenant_id, agent_version_id=active_version_id
        )
        rows = await self.tools_repository.list_published_tool_configs_with_tools_by_config_ids(
            tenant_id=tenant_id,
            tool_config_ids=[binding.tool_config_id for binding in bindings],
        )
        skills: list[A2AAgentSkill] = []
        for tool_config, tool in rows:
            config = tool_config.config or {}
            operation_id = str(config.get("operation_id") or "")
            skill_id = operation_id or str(tool_config.tool_config_id)
            skills.append(
                A2AAgentSkill(
                    id=skill_id,
                    name=str(tool.name or skill_id),
                    description=str(config.get("summary") or config.get("description") or ""),
                    tags=["tool"],
                )
            )

        return A2AAgentCard(
            protocol_version=A2A_PROTOCOL_VERSION,
            name=str(agent.name or f"agent-{agent_id}"),
            description=str(agent_version.description or ""),
            url=self._rpc_url(agent_id),
            version=(
                f"{agent_version.version_major}."
                f"{agent_version.version_minor}."
                f"{agent_version.version_patch}"
            ),
            capabilities=A2AAgentCapabilities(
                streaming=False,
                push_notifications=False,
                state_transition_history=True,
            ),
            security_schemes={
                "bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
            security=[{"bearer": []}],
            default_input_modes=["text/plain", "application/json"],
            default_output_modes=["text/plain", "application/json"],
            skills=skills,
        )
