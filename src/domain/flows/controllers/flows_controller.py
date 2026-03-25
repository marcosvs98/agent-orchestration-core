from fastapi import APIRouter, Depends, Header, Query, status
from uuid import UUID

from domain.common.schemas.change import ChangeRequest
from domain.flows.schemas.flows import (
    ConditionExpression,
    ConditionExpressionCreate,
    CustomNodeCreate,
    DeploymentComposeRequest,
    DeploymentComposeResponse,
    DeploymentComposeValidateResponse,
    Flow,
    FlowArtifactsBatchUpsertRequest,
    FlowArtifactsBatchUpsertResponse,
    FlowCreate,
    FlowVersion,
    FlowVersionCreate,
    Node,
    NodeCreate,
    NodeTemplateCatalogItem,
    NodeTemplateCopyRequest,
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
from exceptions.service_exceptions import (
    MethodNotAllowedPlaceholderException,
    RouterValidationException,
)
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
        r(
            "/flows",
            self.list_flows,
            methods=["GET"],
            response_model=list[Flow],
        )
        r(
            "/flows",
            self.create_flow,
            methods=["POST"],
            response_model=Flow,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/node-templates:system",
            self.list_system_node_templates,
            methods=["GET"],
            response_model=list[NodeTemplateCatalogItem],
        )
        r(
            "/flows/{flow_id}",
            self.get_flow,
            methods=["GET"],
            response_model=Flow,
        )
        r(
            "/flows/{flow_id}/versions",
            self.list_flow_versions,
            methods=["GET"],
            response_model=list[FlowVersion],
        )
        r(
            "/flows/{flow_id}/versions",
            self.create_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:validate",
            self.validate_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:publish",
            self.publish_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:activate",
            self.activate_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:rollback",
            self.rollback_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:deprecate",
            self.deprecate_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}:disable",
            self.disable_flow_version,
            methods=["POST"],
            response_model=FlowVersion,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/nodes",
            self.list_nodes,
            methods=["GET"],
            response_model=list[Node],
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/graph",
            self.create_flow_graph,
            methods=["POST"],
            response_model=None,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/graph:draft",
            self.upsert_flow_graph_draft,
            methods=["POST"],
            response_model=None,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/graph:validate",
            self.validate_flow_graph_draft,
            methods=["POST"],
            response_model=None,
            status_code=status.HTTP_200_OK,
            responses=self._resp405(),
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/graph:compile",
            self.compile_flow_graph,
            methods=["POST"],
            response_model=None,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/nodes",
            self.create_node,
            methods=["POST"],
            response_model=Node,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/nodes:copy-from-template",
            self.copy_node_from_template,
            methods=["POST"],
            response_model=Node,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/nodes:custom",
            self.create_custom_node,
            methods=["POST"],
            response_model=Node,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/deployments:compose",
            self.compose_deployment,
            methods=["POST"],
            response_model=DeploymentComposeResponse,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/deployments:validate",
            self.validate_compose_deployment,
            methods=["POST"],
            response_model=DeploymentComposeValidateResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/flows/{flow_id}/versions/{flow_version_id}/artifacts:batch-upsert",
            self.batch_upsert_artifacts,
            methods=["PUT"],
            response_model=FlowArtifactsBatchUpsertResponse,
            status_code=status.HTTP_200_OK,
        )
        r(
            "/routers",
            self.list_routers,
            methods=["GET"],
            response_model=list[Router],
        )
        r(
            "/routers",
            self.create_router,
            methods=["POST"],
            response_model=Router,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/routing-rules",
            self.create_routing_rule,
            methods=["POST"],
            response_model=RoutingRule,
            status_code=status.HTTP_201_CREATED,
        )
        r(
            "/condition-expressions",
            self.create_condition_expression,
            methods=["POST"],
            response_model=ConditionExpression,
            status_code=status.HTTP_201_CREATED,
        )

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def list_flows(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[Flow]:
        return await self.service.list_flows(tenant_id=auth.tenant_id, limit=limit)

    async def create_flow(
        self, flow_create: FlowCreate, auth: AuthContext = Depends(get_auth_context)
    ) -> Flow:
        return await self.service.create_flow(
            tenant_id=auth.tenant_id,
            flow_create=flow_create,
            principal_id=auth.principal_id,
        )

    async def get_flow(
        self, flow_id: str, auth: AuthContext = Depends(get_auth_context)
    ) -> Flow:
        return await self.service.get_flow(tenant_id=auth.tenant_id, flow_id=flow_id)

    async def list_flow_versions(
        self,
        flow_id: str,
        status_filter: list[str] | None = Query(default=None),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[FlowVersion]:
        return await self.service.list_flow_versions(
            tenant_id=auth.tenant_id, flow_id=flow_id, status_filter=status_filter
        )

    async def create_flow_version(
        self,
        flow_id: str,
        flow_version_create: FlowVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowVersion:
        return await self.service.create_flow_version(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_create=flow_version_create,
            principal_id=auth.principal_id,
        )

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
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
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
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.upsert_flow_graph_draft(
            tenant_id=auth.tenant_id, payload=payload
        )

    async def validate_flow_graph_draft(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphCompileRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.validate_flow_graph_draft(
            tenant_id=auth.tenant_id, payload=payload
        )

    async def compile_flow_graph(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowGraphCompileRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> None:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        await self.service.compile_flow_graph(tenant_id=auth.tenant_id, payload=payload)

    async def list_nodes(
        self,
        flow_id: str,
        flow_version_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[Node]:
        return await self.service.list_nodes(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
        )

    async def create_node(
        self, node_create: NodeCreate, auth: AuthContext = Depends(get_auth_context)
    ) -> Node:
        return await self.service.create_node(
            tenant_id=auth.tenant_id,
            node_create=node_create,
            principal_id=auth.principal_id,
        )

    async def list_system_node_templates(
        self,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[NodeTemplateCatalogItem]:
        return await self.service.list_system_node_templates(tenant_id=auth.tenant_id)

    async def copy_node_from_template(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: NodeTemplateCopyRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> Node:
        return await self.service.copy_node_from_template_request(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            payload=payload,
            principal_id=auth.principal_id,
        )

    async def create_custom_node(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: CustomNodeCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> Node:
        return await self.service.create_custom_node(
            tenant_id=auth.tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            payload=payload,
            principal_id=auth.principal_id,
        )

    async def compose_deployment(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: DeploymentComposeRequest,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DeploymentComposeResponse:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        if not idempotency_key or not idempotency_key.strip():
            raise RouterValidationException(errors=["idempotency_key_required"])
        return await self.service.compose_deployment(
            tenant_id=auth.tenant_id,
            payload=payload,
            idempotency_key=idempotency_key.strip(),
        )

    async def batch_upsert_artifacts(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: FlowArtifactsBatchUpsertRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowArtifactsBatchUpsertResponse:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        return await self.service.batch_upsert_artifacts(
            tenant_id=auth.tenant_id,
            payload=payload,
        )

    async def validate_compose_deployment(
        self,
        flow_id: str,
        flow_version_id: str,
        payload: DeploymentComposeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> DeploymentComposeValidateResponse:
        if payload.flow_id != UUID(flow_id) or payload.flow_version_id != UUID(
            flow_version_id
        ):
            raise RouterValidationException(errors=["flow_id_or_version_mismatch"])
        return await self.service.validate_compose_deployment(
            tenant_id=auth.tenant_id,
            payload=payload,
        )

    async def list_routers(
        self,
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[Router]:
        return await self.service.list_routers(tenant_id=auth.tenant_id, limit=limit)

    async def create_router(
        self, router_create: RouterCreate, auth: AuthContext = Depends(get_auth_context)
    ) -> Router:
        return await self.service.create_router(
            tenant_id=auth.tenant_id,
            router_create=router_create,
            principal_id=auth.principal_id,
        )

    async def create_routing_rule(
        self,
        routing_rule_create: RoutingRuleCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RoutingRule:
        return await self.service.create_routing_rule(
            tenant_id=auth.tenant_id,
            routing_rule_create=routing_rule_create,
            principal_id=auth.principal_id,
        )

    async def create_condition_expression(
        self,
        condition_expression_create: ConditionExpressionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> ConditionExpression:
        return await self.service.create_condition_expression(
            tenant_id=auth.tenant_id,
            condition_expression_create=condition_expression_create,
            principal_id=auth.principal_id,
        )
