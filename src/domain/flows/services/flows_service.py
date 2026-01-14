from domain.flows.ports.service import FlowsServicePort
from exceptions.service_exceptions import NotImplementedServiceException

from uuid import UUID

from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.flows.ports.service import FlowsServicePort
from domain.flows.repositories.flows_repository import FlowsRepository
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.governance.repositories.authoring_event_repository import AuthoringEventRepository
from domain.flows.schemas.graph import (
    FlowGraphCompileRequest,
    FlowGraphCreate,
    FlowGraphDefinition,
    FlowGraphDraftCreate,
)
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler
from domain.flows.services.flow_graph_draft_validator import FlowGraphDraftValidator
from domain.flows.services.flow_graph_validator import FlowGraphValidator
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class FlowsService(FlowsServicePort):
    def __init__(
        self,
        repository: FlowsRepository,
        limit_policy_repository: ExecutionLimitPolicyRepository,
        authoring_events: AuthoringEventRepository,
    ) -> None:
        self.repository = repository
        self.limit_policy_repository = limit_policy_repository
        self.authoring_events = authoring_events
        self.compiler = FlowGraphCompiler()

    async def create_flow_graph(
        self,
        *,
        tenant_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        principal_id: str,
        definition: FlowGraphDefinition,
    ):
        flow = await self.repository.get_flow(flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(flow_version_id)
        if version is None or version.flow_id != flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="flow_version_not_published")

        FlowGraphValidator.validate(definition)
        existing = await self.repository.get_flow_graph_by_flow_version(flow_version_id)
        if existing:
            raise ResourceBlockedServiceException(message="flow_graph_already_exists")

        graph = await self.repository.create_flow_graph(
            flow_version_id=flow_version_id,
            definition=definition.model_dump(),
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow_graph",
            resource_id=flow_id,
            version_id=flow_version_id,
            event_type="FLOW_GRAPH_ATTACHED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="attach flow graph",
            schema_version=1,
        )
        return graph

    async def upsert_flow_graph_draft(
        self,
        *,
        tenant_id: UUID,
        payload: FlowGraphDraftCreate,
    ):
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(payload.flow_version_id)
        if version is None or version.flow_id != payload.flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        FlowGraphValidator.validate(payload.definition)
        draft = await self.repository.upsert_flow_graph_draft(
            flow_version_id=payload.flow_version_id,
            definition=payload.definition.model_dump(),
            principal_id=payload.principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow_graph_draft",
            resource_id=payload.flow_id,
            version_id=payload.flow_version_id,
            event_type="FLOW_GRAPH_DRAFT_SAVED",
            change_type="UPDATE",
            principal_id=payload.principal_id,
            justification="save flow graph draft",
            schema_version=1,
        )
        return draft

    async def validate_flow_graph_draft(
        self,
        *,
        tenant_id: UUID,
        payload: FlowGraphCompileRequest,
    ):
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        draft = await self.repository.get_flow_graph_draft(payload.flow_version_id)
        if draft is None:
            raise NotFoundServiceException(message="flow_graph_draft_not_found")
        definition = FlowGraphDefinition.model_validate(draft.definition)
        FlowGraphDraftValidator.validate(definition)
        validated = await self.repository.validate_flow_graph_draft(
            flow_version_id=payload.flow_version_id,
            principal_id=payload.principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow_graph_draft",
            resource_id=payload.flow_id,
            version_id=payload.flow_version_id,
            event_type="FLOW_GRAPH_DRAFT_VALIDATED",
            change_type="UPDATE",
            principal_id=payload.principal_id,
            justification="validate flow graph draft",
            schema_version=1,
        )
        return validated

    async def compile_flow_graph(
        self,
        *,
        tenant_id: UUID,
        payload: FlowGraphCompileRequest,
    ):
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(payload.flow_version_id)
        if version is None or version.flow_id != payload.flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="flow_version_not_published")
        draft = await self.repository.get_flow_graph_draft(payload.flow_version_id)
        if draft is None:
            raise NotFoundServiceException(message="flow_graph_draft_not_found")
        if draft.status != "VALIDATED":
            raise ResourceBlockedServiceException(message="flow_graph_draft_not_validated")
        definition = FlowGraphDefinition.model_validate(draft.definition)
        FlowGraphDraftValidator.validate(definition)
        snapshot_payload, graph_hash = self.compiler.compile(definition)
        snapshot = await self.repository.create_flow_graph_snapshot(
            flow_version_id=payload.flow_version_id,
            snapshot=snapshot_payload,
            graph_hash=graph_hash,
            compiled_by=payload.principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow_graph_snapshot",
            resource_id=payload.flow_id,
            version_id=payload.flow_version_id,
            event_type="FLOW_GRAPH_COMPILED",
            change_type="UPDATE",
            principal_id=payload.principal_id,
            justification="compile flow graph snapshot",
            schema_version=1,
        )
        return snapshot

    async def validate_flow_version(self, *, tenant_id: UUID, flow_id: str, flow_version_id: str):
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.DRAFT:
            raise ResourceBlockedServiceException(message="flow_version_not_draft")

        nodes = await self.repository.list_nodes_for_flow_version(version_uuid)
        if not nodes:
            raise DomainValidationException(message="flow_version_has_no_nodes")

        node_ids = {n.node_id for n in nodes}
        rules = await self.repository.list_routing_rules_for_flow_version(version_uuid)
        for rule in rules:
            if rule.from_node_id not in node_ids or rule.to_node_id not in node_ids:
                raise DomainValidationException(message="routing_rule_cross_version")

        adjacency: dict[UUID, set[UUID]] = {nid: set() for nid in node_ids}
        for rule in rules:
            adjacency[rule.from_node_id].add(rule.to_node_id)

        visited: set[UUID] = set()
        stack: set[UUID] = set()

        def dfs(nid: UUID) -> None:
            visited.add(nid)
            stack.add(nid)
            for nxt in adjacency.get(nid, set()):
                if nxt not in visited:
                    dfs(nxt)
                elif nxt in stack:
                    raise DomainValidationException(message="cycle_detected")
            stack.remove(nid)

        for nid in node_ids:
            if nid not in visited:
                dfs(nid)

        policy = await self.limit_policy_repository.get_default_policy_for_tenant(tenant_id)
        if policy is None:
            raise ResourceBlockedServiceException(message="execution_limit_policy_not_configured")
        published = await self.limit_policy_repository.get_published_policy_version(
            policy.execution_limit_policy_id
        )
        if published is None:
            raise ResourceBlockedServiceException(message="execution_limit_policy_not_published")

        await self.repository.set_flow_version_status(
            flow_version_id=version_uuid, status=VersionStatus.VALIDATED
        )
        refreshed = await self.repository.get_flow_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        return refreshed

    async def publish_flow_version(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.VALIDATED:
            raise ResourceBlockedServiceException(message="flow_version_not_validated")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_flow_version_status(
            flow_version_id=version_uuid, status=VersionStatus.PUBLISHED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow",
            resource_id=flow_uuid,
            version_id=version_uuid,
            event_type="VERSION_PUBLISHED",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_flow_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        return refreshed

    async def activate_flow_version(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="flow_version_not_published")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(version_uuid)
        if snapshot is None:
            raise ResourceBlockedServiceException(message="flow_graph_snapshot_missing")
        await self.repository.upsert_active_flow_version(
            flow_id=flow_uuid,
            flow_version_id=version_uuid,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
            flow_graph_snapshot_id=snapshot.flow_graph_snapshot_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow",
            resource_id=flow_uuid,
            version_id=version_uuid,
            event_type="VERSION_ACTIVATED",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return version

    async def rollback_flow_version(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="flow_version_not_published")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(version_uuid)
        if snapshot is None:
            raise ResourceBlockedServiceException(message="flow_graph_snapshot_missing")
        await self.repository.upsert_active_flow_version(
            flow_id=flow_uuid,
            flow_version_id=version_uuid,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
            flow_graph_snapshot_id=snapshot.flow_graph_snapshot_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow",
            resource_id=flow_uuid,
            version_id=version_uuid,
            event_type="VERSION_ROLLED_BACK",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return version
    async def list_flows(self):
        raise NotImplementedServiceException()

    async def create_flow(self, flow_create):
        raise NotImplementedServiceException()

    async def get_flow(self, flow_id: str):
        raise NotImplementedServiceException()

    async def list_flow_versions(self, flow_id: str):
        raise NotImplementedServiceException()

    async def create_flow_version(self, flow_id: str, flow_version_create):
        raise NotImplementedServiceException()

    async def list_nodes(self, flow_id: str, flow_version_id: str):
        raise NotImplementedServiceException()

    async def create_node(self, node_create):
        raise NotImplementedServiceException()

    async def list_routers(self):
        raise NotImplementedServiceException()

    async def create_router(self, router_create):
        raise NotImplementedServiceException()

    async def create_routing_rule(self, routing_rule_create):
        raise NotImplementedServiceException()

    async def create_condition_expression(self, condition_expression_create):
        raise NotImplementedServiceException()
