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
        await self._resolve_binding(node_id, state, required_key=self._prompt_key(node_id))
        return state.get(self._prompt_key(node_id))

    async def resolve_agent_version_id(
        self,
        node_id: UUID,
        state: dict[str, Any],
    ) -> UUID | None:
        """Which agent version governs this node, for run and usage attribution."""

        await self._resolve_binding(node_id, state, required_key=self._version_key(node_id))
        return state.get(self._version_key(node_id))

    @staticmethod
    def _prompt_key(node_id: UUID) -> str:
        return f"_agent_system_prompt_{node_id}"

    @staticmethod
    def _version_key(node_id: UUID) -> str:
        return f"_agent_version_id_{node_id}"

    async def _resolve_binding(
        self, node_id: UUID, state: dict[str, Any], *, required_key: str
    ) -> None:
        """Load the node's agent binding once per flow run, caching prompt and version in state.

        Only the requested key gates the lookup, so a graph state written before the version key
        existed still short-circuits on the prompt it already carries.
        """

        if required_key in state:
            return
        prompt_key = self._prompt_key(node_id)
        version_key = self._version_key(node_id)
        state.setdefault(prompt_key, None)
        state.setdefault(version_key, None)
        agent_version_id = await self.agents_repository.get_agent_version_id_by_node_id(node_id)
        if agent_version_id is None:
            return
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            return
        state[version_key] = agent_version_id
        state[prompt_key] = (agent_version.system_prompt or "").strip() or None
