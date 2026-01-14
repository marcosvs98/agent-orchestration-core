from fastapi import APIRouter, Depends, status

from domain.common.schemas.change import ChangeRequest
from domain.agents.schemas.agents import (
    Agent,
    AgentCreate,
    AgentVersion,
    AgentVersionCreate,
    NodeAgentBinding,
    NodeAgentBindingCreate,
)
from domain.agents.services.agents_service import AgentsService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException
from utils.auth import AuthContext, get_auth_context


class AgentsController:
    """HTTP controller for agents."""

    def __init__(self, service: AgentsService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["agents"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r("/agents", self.list_agents, methods=["GET"], response_model=list[Agent], responses=self._resp405())
        r("/agents", self.create_agent, methods=["POST"], response_model=Agent, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/agents/{agent_id}/versions", self.list_agent_versions, methods=["GET"], response_model=list[AgentVersion], responses=self._resp405())
        r("/agents/{agent_id}/versions", self.create_agent_version, methods=["POST"], response_model=AgentVersion, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:validate", self.validate_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:publish", self.publish_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:activate", self.activate_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:rollback", self.rollback_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:deprecate", self.deprecate_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/agents/{agent_id}/versions/{agent_version_id}:disable", self.disable_agent_version, methods=["POST"], response_model=AgentVersion, responses=self._resp405())
        r("/node-agent-bindings", self.create_node_agent_binding, methods=["POST"], response_model=NodeAgentBinding, status_code=status.HTTP_201_CREATED, responses=self._resp405())

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_agents(self, _: AuthContext = Depends(get_auth_context)) -> list[Agent]:
        raise MethodNotAllowedPlaceholderException()

    async def create_agent(self, __: AgentCreate, _: AuthContext = Depends(get_auth_context)) -> Agent:
        raise MethodNotAllowedPlaceholderException()

    async def list_agent_versions(
        self,
        agent_id: str,
        status_filter: list[str] | None = None,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[AgentVersion]:
        raise MethodNotAllowedPlaceholderException()

    async def create_agent_version(
        self,
        agent_id: str,
        __: AgentVersionCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        raise MethodNotAllowedPlaceholderException()

    async def validate_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        model = await self.service.validate_agent_version(
            tenant_id=auth.tenant_id, agent_id=agent_id, agent_version_id=agent_version_id
        )
        return AgentVersion(
            id=model.agent_version_id,
            agent_id=model.agent_id,
            description=None,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            supported_tool_schema_version=model.supported_tool_schema_version,
            supported_tool_config_hash_prefix=model.supported_tool_config_hash_prefix,
        )

    async def publish_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        model = await self.service.publish_agent_version(
            tenant_id=auth.tenant_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return AgentVersion(
            id=model.agent_version_id,
            agent_id=model.agent_id,
            description=None,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            supported_tool_schema_version=model.supported_tool_schema_version,
            supported_tool_config_hash_prefix=model.supported_tool_config_hash_prefix,
        )

    async def activate_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        model = await self.service.activate_agent_version(
            tenant_id=auth.tenant_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return AgentVersion(
            id=model.agent_version_id,
            agent_id=model.agent_id,
            description=None,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            supported_tool_schema_version=model.supported_tool_schema_version,
            supported_tool_config_hash_prefix=model.supported_tool_config_hash_prefix,
        )

    async def rollback_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        model = await self.service.rollback_agent_version(
            tenant_id=auth.tenant_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return AgentVersion(
            id=model.agent_version_id,
            agent_id=model.agent_id,
            description=None,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            supported_tool_schema_version=model.supported_tool_schema_version,
            supported_tool_config_hash_prefix=model.supported_tool_config_hash_prefix,
        )

    async def deprecate_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        raise MethodNotAllowedPlaceholderException()

    async def disable_agent_version(
        self,
        agent_id: str,
        agent_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> AgentVersion:
        raise MethodNotAllowedPlaceholderException()

    async def create_node_agent_binding(
        self,
        __: NodeAgentBindingCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> NodeAgentBinding:
        raise MethodNotAllowedPlaceholderException()
