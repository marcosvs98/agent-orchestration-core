from __future__ import annotations

from typing import Any
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository


class AgentRuntimeResolver:
    def __init__(self, agents_repository: AgentsRepository) -> None:
        self.agents_repository = agents_repository

    async def resolve_system_prompt(
        self,
        flow_run_id: UUID,
        node_id: UUID,
        state: dict[str, Any],
    ) -> str | None:
        key = f"_agent_system_prompt_{node_id}"
        if key in state:
            return state[key]
        agent_version_id = await self.agents_repository.get_agent_version_id_by_node_id(
            node_id
        )
        if agent_version_id is None:
            state[key] = None
            return None
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            state[key] = None
            return None
        system_prompt = (agent_version.system_prompt or "").strip() or None
        state[key] = system_prompt
        return system_prompt
