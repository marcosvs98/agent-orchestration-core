from fastapi import APIRouter, Depends, status
from uuid import UUID

from domain.common.schemas.change import ChangeRequest
from domain.flows.schemas.flows import (
    ConditionExpression,
    ConditionExpressionCreate,
    Flow,
    FlowCreate,
    FlowVersion,
    FlowVersionCreate,
    Node,
    NodeCreate,
    Router,
    RouterCreate,
    RoutingRule,
    RoutingRuleCreate,
)
from domain.flows.schemas.graph import (
    FlowGraphCompileRequest,
    FlowGraphCreate,
    FlowGraphDefinition,
    FlowGraphDraftCreate,
)
from domain.flows.services.flows_service import FlowsService
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import MethodNotAllowedPlaceholderException, RouterValidationException
from utils.auth import AuthContext, get_auth_context


class FlowsController:
    """HTTP controller for flows, nodes, and routing."""

    def __init__(self, service: FlowsService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["flows", "nodes", "routing"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r("/flows", self.list_flows, methods=["GET"], response_model=list[Flow], responses=self._resp405())
        r("/flows", self.create_flow, methods=["POST"], response_model=Flow, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/flows/{flow_id}", self.get_flow, methods=["GET"], response_model=Flow, responses=self._resp405())
        r("/flows/{flow_id}/versions", self.list_flow_versions, methods=["GET"], response_model=list[FlowVersion], responses=self._resp405())
        r("/flows/{flow_id}/versions", self.create_flow_version, methods=["POST"], response_model=FlowVersion, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:validate", self.validate_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:publish", self.publish_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:activate", self.activate_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:rollback", self.rollback_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:deprecate", self.deprecate_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}:disable", self.disable_flow_version, methods=["POST"], response_model=FlowVersion, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}/nodes", self.list_nodes, methods=["GET"], response_model=list[Node], responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}/graph", self.create_flow_graph, methods=["POST"], response_model=None, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}/graph:draft", self.upsert_flow_graph_draft, methods=["POST"], response_model=None, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}/graph:validate", self.validate_flow_graph_draft, methods=["POST"], response_model=None, status_code=status.HTTP_200_OK, responses=self._resp405())
        r("/flows/{flow_id}/versions/{flow_version_id}/graph:compile", self.compile_flow_graph, methods=["POST"], response_model=None, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/nodes", self.create_node, methods=["POST"], response_model=Node, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/routers", self.list_routers, methods=["GET"], response_model=list[Router], responses=self._resp405())
        r("/routers", self.create_router, methods=["POST"], response_model=Router, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/routing-rules", self.create_routing_rule, methods=["POST"], response_model=RoutingRule, status_code=status.HTTP_201_CREATED, responses=self._resp405())
        r("/condition-expressions", self.create_condition_expression, methods=["POST"], response_model=ConditionExpression, status_code=status.HTTP_201_CREATED, responses=self._resp405())

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_flows(self, _: AuthContext = Depends(get_auth_context)) -> list[Flow]:
        raise MethodNotAllowedPlaceholderException()

    async def create_flow(self, __: FlowCreate, _: AuthContext = Depends(get_auth_context)) -> Flow:
        raise MethodNotAllowedPlaceholderException()

    async def get_flow(self, flow_id: str, _: AuthContext = Depends(get_auth_context)) -> Flow:
        raise MethodNotAllowedPlaceholderException()

    async def list_flow_versions(
        self,
        flow_id: str,
        status_filter: list[str] | None = None,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[FlowVersion]:
        raise MethodNotAllowedPlaceholderException()

    async def create_flow_version(
        self,
        flow_id: str,
        __: FlowVersionCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        raise MethodNotAllowedPlaceholderException()

    async def validate_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        model = await self.service.validate_flow_version(
            tenant_id=auth.tenant_id, flow_id=flow_id, flow_version_id=flow_version_id
        )
        return FlowVersion(
            id=model.flow_version_id,
            flow_id=model.flow_id,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            min_agent_version_major=model.min_agent_version_major,
            min_agent_version_minor=model.min_agent_version_minor,
            min_agent_version_patch=model.min_agent_version_patch,
        )

    async def publish_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        model = await self.service.publish_flow_version(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return FlowVersion(
            id=model.flow_version_id,
            flow_id=model.flow_id,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            min_agent_version_major=model.min_agent_version_major,
            min_agent_version_minor=model.min_agent_version_minor,
            min_agent_version_patch=model.min_agent_version_patch,
        )

    async def activate_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        model = await self.service.activate_flow_version(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return FlowVersion(
            id=model.flow_version_id,
            flow_id=model.flow_id,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            min_agent_version_major=model.min_agent_version_major,
            min_agent_version_minor=model.min_agent_version_minor,
            min_agent_version_patch=model.min_agent_version_patch,
        )

    async def rollback_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        model = await self.service.rollback_flow_version(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
        return FlowVersion(
            id=model.flow_version_id,
            flow_id=model.flow_id,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            min_agent_version_major=model.min_agent_version_major,
            min_agent_version_minor=model.min_agent_version_minor,
            min_agent_version_patch=model.min_agent_version_patch,
        )

    async def deprecate_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        raise MethodNotAllowedPlaceholderException()

    async def disable_flow_version(
        self,
        flow_id: str,
        flow_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        raise MethodNotAllowedPlaceholderException()

    async def create_flow_graph(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(flow_version_id):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.create_flow_graph(
            tenant_id=auth.tenant_id,
            flow_id=UUID(flow_id),
            flow_version_id=UUID(flow_version_id),
            principal_id=auth.principal_id,
            definition=FlowGraphDefinition.model_validate(payload.definition),
        )

    async def upsert_flow_graph_draft(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphDraftCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(flow_version_id):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.upsert_flow_graph_draft(tenant_id=auth.tenant_id, payload=payload)

    async def validate_flow_graph_draft(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphCompileRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(flow_version_id):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.validate_flow_graph_draft(tenant_id=auth.tenant_id, payload=payload)

    async def compile_flow_graph(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphCompileRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(flow_version_id):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.compile_flow_graph(tenant_id=auth.tenant_id, payload=payload)

    async def list_nodes(
        self,
        flow_id: str,
        flow_version_id: str,
        _: AuthContext = Depends(get_auth_context),
    ) -> list[Node]:
        raise MethodNotAllowedPlaceholderException()

    async def create_node(self, __: NodeCreate, _: AuthContext = Depends(get_auth_context)) -> Node:
        raise MethodNotAllowedPlaceholderException()

    async def list_routers(self, _: AuthContext = Depends(get_auth_context)) -> list[Router]:
        raise MethodNotAllowedPlaceholderException()

    async def create_router(self, __: RouterCreate, _: AuthContext = Depends(get_auth_context)) -> Router:
        raise MethodNotAllowedPlaceholderException()

    async def create_routing_rule(
        self,
        __: RoutingRuleCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> RoutingRule:
        raise MethodNotAllowedPlaceholderException()

    async def create_condition_expression(
        self,
        __: ConditionExpressionCreate,
        _: AuthContext = Depends(get_auth_context),
    ) -> ConditionExpression:
        raise MethodNotAllowedPlaceholderException()
