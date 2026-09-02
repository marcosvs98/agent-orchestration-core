from __future__ import annotations

import hashlib
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import PersonaConfig
from domain.common.schemas.versioning import VersionStatus
from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.tools.services.agent_tool_catalog import AgentToolBinding, AgentToolCatalog
from exceptions.service_exceptions import (
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class AgentDefinition(BaseModel):
    """The persistent configuration a run executes against, resolved once and then frozen.

    Resolution follows the same gates the flow path applies (active and published agent version,
    published AI execution policy, active billing policy), so a direct run cannot quietly execute
    a draft configuration that a flow would have refused.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: UUID
    agent_name: str | None
    agent_version_id: UUID
    system_prompt: str | None
    persona_config: PersonaConfig | None
    model_name: str
    ai_execution_policy_version_id: UUID
    billing_policy_version_id: UUID
    tools: list[AgentToolBinding]

    def system_prompt_hash(self) -> str | None:
        base = (self.system_prompt or "").strip()
        if not base:
            return None
        return hashlib.sha256(base.encode()).hexdigest()

    def runtime_snapshot(self) -> dict[str, object]:
        return {
            "agent_id": str(self.agent_id),
            "agent_version_id": str(self.agent_version_id),
            "ai_execution_policy_version_id": str(self.ai_execution_policy_version_id),
            "billing_policy_version_id": str(self.billing_policy_version_id),
            "model": self.model_name,
            "tool_function_names": sorted(tool.function_name for tool in self.tools),
        }


class AgentDefinitionResolver:
    def __init__(
        self,
        agents_repository: AgentsRepository,
        execution_repository: ExecutionRepository,
        tool_catalog: AgentToolCatalog,
    ) -> None:
        self.agents_repository = agents_repository
        self.execution_repository = execution_repository
        self.tool_catalog = tool_catalog

    async def resolve(self, *, tenant_id: UUID, agent_id: UUID) -> AgentDefinition:
        agent = await self.agents_repository.get_agent(agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")

        agent_version_id = await self.agents_repository.get_active_agent_version_id(agent_id)
        if agent_version_id is None:
            raise ResourceBlockedServiceException(message="agent_version_not_active")
        agent_version = await self.agents_repository.get_agent_version(agent_version_id)
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        if agent_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="agent_version_blocked")

        if agent_version.ai_execution_policy_version_id is None:
            raise ResourceBlockedServiceException(message="ai_execution_policy_not_active")
        policy_version = await self.execution_repository.get_ai_execution_policy_version(
            agent_version.ai_execution_policy_version_id
        )
        if policy_version is None:
            raise NotFoundServiceException(message="ai_execution_policy_version_not_found")
        if policy_version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="ai_execution_policy_blocked")
        model_record = await self.execution_repository.get_model(policy_version.model_id)
        if model_record is None or not model_record.name:
            raise NotFoundServiceException(message="model_not_found")

        billing_policy_version_id = (
            await self.execution_repository.get_active_billing_policy_version_id(tenant_id)
        )
        if billing_policy_version_id is None:
            raise ResourceBlockedServiceException(message="billing_policy_not_active")

        persona_config = None
        if agent_version.persona_config:
            persona_config = PersonaConfig.model_validate(agent_version.persona_config)

        tools = await self.tool_catalog.list_agent_version_tools(
            tenant_id=tenant_id, agent_version_id=agent_version_id
        )

        return AgentDefinition(
            agent_id=agent_id,
            agent_name=agent.name,
            agent_version_id=agent_version_id,
            system_prompt=agent_version.system_prompt,
            persona_config=persona_config,
            model_name=model_record.name,
            ai_execution_policy_version_id=agent_version.ai_execution_policy_version_id,
            billing_policy_version_id=billing_policy_version_id,
            tools=tools,
        )
