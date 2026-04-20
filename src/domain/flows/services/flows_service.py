import hashlib
import json
from typing import Any
from uuid import UUID

from domain.flows.ports.service import FlowsServicePort

from domain.execution.adapters.idempotency_service import IdempotencyService
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus

from domain.flows.repositories.flows_repository import FlowsRepository
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
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
    FlowGraphDefinition,
    FlowGraphDraftCreate,
    FlowGraphNodeSpec,
)
from domain.flows.schemas.graph_node_config import validate_node_config
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler
from domain.flows.services.flow_graph_draft_validator import FlowGraphDraftValidator
from domain.flows.services.flow_graph_validator import FlowGraphValidator
from domain.governance.services.rag_policy_service import RagPolicyService
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.services.rag_flow_snapshot_materialization import (
    resolve_frozen_rag_snapshot_fields,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    IdempotencyInProgressException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class FlowsService(FlowsServicePort):
    def __init__(
        self,
        repository: FlowsRepository,
        limit_policy_repository: ExecutionLimitPolicyRepository,
        authoring_events: AuthoringEventRepository,
        idempotency: IdempotencyService,
        rag_repository: RagRepository | None = None,
        rag_policy_service: RagPolicyService | None = None,
    ) -> None:
        self.repository = repository
        self.limit_policy_repository = limit_policy_repository
        self.authoring_events = authoring_events
        self.idempotency = idempotency
        self.rag_repository = rag_repository
        self.rag_policy_service = rag_policy_service
        self.compiler = FlowGraphCompiler()

    @staticmethod
    def _hash_dict(payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _unique_rag_config_id_for_flow_nodes(nodes: list[Any]) -> UUID | None:
        found: UUID | None = None
        for node in nodes:
            rid = node.rag_config_id
            if rid is None:
                continue
            if found is None:
                found = rid
            elif found != rid:
                raise DomainValidationException(
                    message="flow_snapshot_rag_config_conflict",
                    name="FLOW_SNAPSHOT_RAG_CONFIG_CONFLICT",
                    input_data={"code": "flow_snapshot_rag_config_conflict"},
                    status_code=422,
                )
        return found

    async def _resolve_frozen_rag_for_flow_version(
        self,
        *,
        tenant_id: UUID,
        flow_version_id: UUID,
    ) -> tuple[UUID | None, UUID | None, UUID | None, str | None]:
        if self.rag_repository is None or self.rag_policy_service is None:
            return None, None, None, None
        nodes = await self.repository.list_nodes_for_flow_version(flow_version_id)
        effective = self._unique_rag_config_id_for_flow_nodes(nodes)
        return await resolve_frozen_rag_snapshot_fields(
            tenant_id=tenant_id,
            rag_config_id=effective,
            rag_repository=self.rag_repository,
            rag_policy_service=self.rag_policy_service,
        )

    async def _assert_at_most_one_allow_memory_write_on_create(
        self,
        *,
        flow_version_id: UUID,
        allow_memory_write: bool,
    ) -> None:
        if not allow_memory_write:
            return
        nodes = await self.repository.list_nodes_for_flow_version(flow_version_id)
        if sum(1 for n in nodes if bool(n.allow_memory_write)) > 0:
            raise DomainValidationException(
                message="multiple_nodes_allow_memory_write",
            )

    async def _assert_flow_version_at_most_one_memory_write(
        self,
        *,
        flow_version_id: UUID,
    ) -> None:
        nodes = await self.repository.list_nodes_for_flow_version(flow_version_id)
        if sum(1 for n in nodes if bool(n.allow_memory_write)) > 1:
            raise DomainValidationException(
                message="multiple_nodes_allow_memory_write",
            )

    async def _materialize_snapshot_for_flow_version(
        self,
        *,
        flow_id: UUID,
        flow_version_id: UUID,
        principal_id: str,
        attach_default_deployment: bool,
    ) -> None:
        fgs = await self.repository.get_flow_graph_snapshot_by_flow_version(flow_version_id)
        if fgs is None:
            return
        flow = await self.repository.get_flow(flow_id)
        if flow is None:
            return
        runtime_policy: dict[str, Any] = {}
        tool_catalog: dict[str, Any] = {}
        binding_rows: list[dict[str, Any]] = []
        (
            fr_cfg,
            fr_rule,
            fr_pol,
            fr_hash,
        ) = await self._resolve_frozen_rag_for_flow_version(
            tenant_id=flow.tenant_id,
            flow_version_id=flow_version_id,
        )
        snapshot_hash = self._hash_dict(
            {
                "graph_hash": fgs.graph_hash,
                "runtime_policy": runtime_policy,
                "tool_catalog": tool_catalog,
                "bindings": binding_rows,
                "frozen_rag_materialization_hash": fr_hash,
            }
        )
        flow_snapshot = await self.repository.upsert_flow_snapshot(
            flow_version_id=flow_version_id,
            snapshot_schema_version=1,
            snapshot_hash=snapshot_hash,
            snapshot={
                "flow_graph_snapshot_id": str(fgs.flow_graph_snapshot_id),
                "graph_hash": fgs.graph_hash,
                "graph": fgs.snapshot,
            },
            runtime_policy=runtime_policy,
            tool_catalog=tool_catalog,
            llm_provider_config_hash=None,
            created_by=principal_id,
            frozen_rag_config_id=fr_cfg,
            frozen_rag_chunking_rule_id=fr_rule,
            frozen_rag_policy_version_id=fr_pol,
            frozen_rag_materialization_hash=fr_hash,
        )
        await self.repository.upsert_snapshot_effective_policy(
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            policy_hash=self._hash_dict(runtime_policy),
            definition=runtime_policy,
        )
        await self.repository.replace_snapshot_bindings(
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            bindings=binding_rows,
        )
        if attach_default_deployment:
            await self.repository.upsert_flow_deployment(
                flow_id=flow_id,
                flow_version_id=flow_version_id,
                flow_snapshot_id=flow_snapshot.flow_snapshot_id,
                environment="default",
                deployed_by=principal_id,
            )

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
        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=payload.flow_version_id,
        )
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
        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=payload.flow_version_id,
        )
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

        draft = await self.repository.get_flow_graph_draft(version_uuid)
        if draft is None:
            raise DomainValidationException(message="flow_graph_draft_not_found")
        if draft.status != "VALIDATED":
            raise DomainValidationException(message="flow_graph_draft_not_validated")

        policy = await self.limit_policy_repository.get_default_policy_for_tenant(tenant_id)
        if policy is None:
            raise ResourceBlockedServiceException(message="execution_limit_policy_not_configured")
        published = await self.limit_policy_repository.get_published_policy_version(
            policy.execution_limit_policy_id
        )
        if published is None:
            raise ResourceBlockedServiceException(message="execution_limit_policy_not_published")

        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=version_uuid,
        )

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
        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=version_uuid,
        )
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
        await self._materialize_snapshot_for_flow_version(
            flow_id=flow_uuid,
            flow_version_id=version_uuid,
            principal_id=principal_id,
            attach_default_deployment=False,
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
        await self._materialize_snapshot_for_flow_version(
            flow_id=flow_uuid,
            flow_version_id=version_uuid,
            principal_id=principal_id,
            attach_default_deployment=True,
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

    async def compose_deployment(
        self,
        *,
        tenant_id: UUID,
        payload: DeploymentComposeRequest,
        idempotency_key: str,
    ) -> DeploymentComposeResponse:
        idem_key = self.idempotency.build_key(
            tenant_id=tenant_id,
            endpoint="flows:deployments:compose",
            idempotency_key=idempotency_key,
        )
        acquired = await self.idempotency.try_acquire(idem_key)
        if not acquired:
            existing = await self.idempotency.get(idem_key)
            if existing and "response" in existing:
                return DeploymentComposeResponse.model_validate(existing["response"])
            raise IdempotencyInProgressException()
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(payload.flow_version_id)
        if version is None or version.flow_id != payload.flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="flow_version_not_published")
        definition = FlowGraphDefinition.model_validate(payload.graph_definition)
        FlowGraphDraftValidator.validate(definition)
        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=payload.flow_version_id,
        )
        snapshot_payload, graph_hash = self.compiler.compile(definition)
        flow_graph_snapshot = await self.repository.get_flow_graph_snapshot_by_flow_version(
            payload.flow_version_id
        )
        if flow_graph_snapshot is None:
            flow_graph_snapshot = await self.repository.create_flow_graph_snapshot(
                flow_version_id=payload.flow_version_id,
                snapshot=snapshot_payload,
                graph_hash=graph_hash,
                compiled_by=payload.principal_id,
            )
        runtime_policy = payload.runtime_policy_definition or {}
        tool_catalog = payload.tool_catalog or {}
        llm_provider_config_hash = payload.llm_provider_config_hash
        (
            fr_cfg,
            fr_rule,
            fr_pol,
            fr_hash,
        ) = await self._resolve_frozen_rag_for_flow_version(
            tenant_id=tenant_id,
            flow_version_id=payload.flow_version_id,
        )
        snapshot_hash = self._hash_dict(
            {
                "graph_hash": flow_graph_snapshot.graph_hash,
                "runtime_policy": runtime_policy,
                "tool_catalog": tool_catalog,
                "bindings": [binding.model_dump(mode="json") for binding in payload.bindings],
                "frozen_rag_materialization_hash": fr_hash,
            }
        )
        flow_snapshot = await self.repository.upsert_flow_snapshot(
            flow_version_id=payload.flow_version_id,
            snapshot_schema_version=1,
            snapshot_hash=snapshot_hash,
            snapshot={
                "flow_graph_snapshot_id": str(flow_graph_snapshot.flow_graph_snapshot_id),
                "graph_hash": flow_graph_snapshot.graph_hash,
                "graph": snapshot_payload,
            },
            runtime_policy=runtime_policy,
            tool_catalog=tool_catalog,
            llm_provider_config_hash=llm_provider_config_hash,
            created_by=payload.principal_id,
            frozen_rag_config_id=fr_cfg,
            frozen_rag_chunking_rule_id=fr_rule,
            frozen_rag_policy_version_id=fr_pol,
            frozen_rag_materialization_hash=fr_hash,
        )
        await self.repository.upsert_snapshot_effective_policy(
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            policy_hash=self._hash_dict(runtime_policy),
            definition=runtime_policy,
        )
        await self.repository.replace_snapshot_bindings(
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            bindings=[binding.model_dump(mode="json") for binding in payload.bindings],
        )
        deployment = await self.repository.upsert_flow_deployment(
            flow_id=payload.flow_id,
            flow_version_id=payload.flow_version_id,
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            environment=payload.environment,
            deployed_by=payload.principal_id,
        )
        result = DeploymentComposeResponse(
            flow_snapshot_id=flow_snapshot.flow_snapshot_id,
            flow_deployment_id=deployment.flow_deployment_id,
            flow_version_id=payload.flow_version_id,
            environment=deployment.environment,
        )
        await self.idempotency.set_result(idem_key, {"response": result.model_dump(mode="json")})
        return result

    async def validate_compose_deployment(
        self, *, tenant_id: UUID, payload: DeploymentComposeRequest
    ) -> DeploymentComposeValidateResponse:
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(payload.flow_version_id)
        if version is None or version.flow_id != payload.flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        definition = FlowGraphDefinition.model_validate(payload.graph_definition)
        FlowGraphDraftValidator.validate(definition)
        await self._assert_flow_version_at_most_one_memory_write(
            flow_version_id=payload.flow_version_id,
        )
        snapshot_payload, graph_hash = self.compiler.compile(definition)
        fr_hash = (
            await self._resolve_frozen_rag_for_flow_version(
                tenant_id=tenant_id,
                flow_version_id=payload.flow_version_id,
            )
        )[3]
        snapshot_hash = self._hash_dict(
            {
                "graph_hash": graph_hash,
                "runtime_policy": payload.runtime_policy_definition or {},
                "tool_catalog": payload.tool_catalog or {},
                "bindings": [binding.model_dump(mode="json") for binding in payload.bindings],
                "frozen_rag_materialization_hash": fr_hash,
            }
        )
        return DeploymentComposeValidateResponse(valid=True, snapshot_hash=snapshot_hash)

    async def batch_upsert_artifacts(
        self, *, tenant_id: UUID, payload: FlowArtifactsBatchUpsertRequest
    ) -> FlowArtifactsBatchUpsertResponse:
        flow = await self.repository.get_flow(payload.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(payload.flow_version_id)
        if version is None or version.flow_id != payload.flow_id:
            raise NotFoundServiceException(message="flow_version_not_found")
        nodes_created = 0
        routers_created = 0
        expressions_created = 0
        rules_created = 0
        for request in payload.nodes_from_templates:
            await self.copy_node_from_template_request(
                tenant_id=tenant_id,
                flow_id=str(payload.flow_id),
                flow_version_id=str(payload.flow_version_id),
                payload=request,
                principal_id=payload.principal_id,
            )
            nodes_created += 1
        for request in payload.custom_nodes:
            await self.create_custom_node(
                tenant_id=tenant_id,
                flow_id=str(payload.flow_id),
                flow_version_id=str(payload.flow_version_id),
                payload=request,
                principal_id=payload.principal_id,
            )
            nodes_created += 1
        for request in payload.routers:
            await self.create_router(
                tenant_id=tenant_id,
                router_create=request,
                principal_id=payload.principal_id,
            )
            routers_created += 1
        for request in payload.condition_expressions:
            await self.create_condition_expression(
                tenant_id=tenant_id,
                condition_expression_create=request,
                principal_id=payload.principal_id,
            )
            expressions_created += 1
        for request in payload.routing_rules:
            await self.create_routing_rule(
                tenant_id=tenant_id,
                routing_rule_create=request,
                principal_id=payload.principal_id,
            )
            rules_created += 1
        return FlowArtifactsBatchUpsertResponse(
            nodes_created=nodes_created,
            routers_created=routers_created,
            condition_expressions_created=expressions_created,
            routing_rules_created=rules_created,
        )

    async def list_flows(self, *, tenant_id: UUID, limit: int = 200) -> list[Flow]:
        flows = await self.repository.list_flows(tenant_id=tenant_id, limit=limit)
        return [
            Flow(
                id=flow.flow_id,
                name=flow.name,
                description=flow.description,
                tags=flow.tags,
                created_by=flow.created_by,
            )
            for flow in flows
        ]

    async def create_flow(
        self, *, tenant_id: UUID, flow_create: FlowCreate, principal_id: str
    ) -> Flow:
        if not flow_create.name or not flow_create.name.strip():
            raise DomainValidationException(message="flow_name_required")

        model = await self.repository.create_flow(
            tenant_id=tenant_id,
            name=flow_create.name.strip(),
            description=flow_create.description,
            tags=flow_create.tags,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow",
            resource_id=model.flow_id,
            version_id=None,
            event_type="FLOW_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create flow",
            schema_version=1,
        )
        return Flow(
            id=model.flow_id,
            name=model.name,
            description=model.description,
            tags=model.tags,
            created_by=model.created_by,
        )

    async def get_flow(self, *, tenant_id: UUID, flow_id: str) -> Flow:
        flow_uuid = UUID(flow_id)
        model = await self.repository.get_flow(flow_uuid)
        if model is None or model.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        return Flow(
            id=model.flow_id,
            name=model.name,
            description=model.description,
            tags=model.tags,
            created_by=model.created_by,
        )

    async def list_flow_versions(
        self, *, tenant_id: UUID, flow_id: str, status_filter: list[str] | None = None
    ) -> list[FlowVersion]:
        flow_uuid = UUID(flow_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        versions = await self.repository.list_flow_versions(
            flow_id=flow_uuid, status_filter=status_filter
        )
        return [
            FlowVersion(
                id=version.flow_version_id,
                flow_id=version.flow_id,
                status=version.status,
                version_major=version.version_major,
                version_minor=version.version_minor,
                version_patch=version.version_patch,
                config_hash=version.config_hash,
                min_agent_version_major=version.min_agent_version_major,
                min_agent_version_minor=version.min_agent_version_minor,
                min_agent_version_patch=version.min_agent_version_patch,
            )
            for version in versions
        ]

    async def create_flow_version(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_create: FlowVersionCreate,
        principal_id: str,
    ) -> FlowVersion:
        flow_uuid = UUID(flow_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        model = await self.repository.create_flow_version(
            flow_id=flow_uuid,
            source_version_id=flow_version_create.source_version_id,
            version_major=flow_version_create.version_major,
            version_minor=flow_version_create.version_minor,
            version_patch=flow_version_create.version_patch,
            min_agent_version_major=flow_version_create.min_agent_version_major,
            min_agent_version_minor=flow_version_create.min_agent_version_minor,
            min_agent_version_patch=flow_version_create.min_agent_version_patch,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="flow",
            resource_id=flow_uuid,
            version_id=model.flow_version_id,
            event_type="FLOW_VERSION_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create flow version",
            schema_version=1,
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

    async def list_nodes(
        self, *, tenant_id: UUID, flow_id: str, flow_version_id: str
    ) -> list[Node]:
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        nodes = await self.repository.list_nodes_for_flow_version(version_uuid)
        return [
            Node(
                id=node.node_id,
                flow_version_id=node.flow_version_id,
                node_prompt_id=node.node_prompt_id,
                allow_rag_tenant=bool(node.allow_rag_tenant),
                allow_user_memory_structured=bool(node.allow_user_memory_structured),
                allow_user_memory_vector=bool(node.allow_user_memory_vector),
                rag_config_id=node.rag_config_id,
                allow_session_context=bool(node.allow_session_context),
                allow_memory_write=bool(node.allow_memory_write),
            )
            for node in nodes
        ]

    async def create_node(
        self, *, tenant_id: UUID, node_create: NodeCreate, principal_id: str
    ) -> Node:
        version = await self.repository.get_flow_version(node_create.flow_version_id)
        if version is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        flow = await self.repository.get_flow(version.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        await self._assert_at_most_one_allow_memory_write_on_create(
            flow_version_id=node_create.flow_version_id,
            allow_memory_write=node_create.allow_memory_write,
        )
        model = await self.repository.create_node(
            flow_version_id=node_create.flow_version_id,
            node_prompt_id=node_create.node_prompt_id,
            allow_rag_tenant=node_create.allow_rag_tenant,
            allow_user_memory_structured=node_create.allow_user_memory_structured,
            allow_user_memory_vector=node_create.allow_user_memory_vector,
            rag_config_id=node_create.rag_config_id,
            allow_session_context=node_create.allow_session_context,
            allow_memory_write=node_create.allow_memory_write,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="node",
            resource_id=model.node_id,
            version_id=node_create.flow_version_id,
            event_type="NODE_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create node",
            schema_version=1,
        )
        return Node(
            id=model.node_id,
            flow_version_id=model.flow_version_id,
            node_prompt_id=model.node_prompt_id,
            allow_rag_tenant=bool(model.allow_rag_tenant),
            allow_user_memory_structured=bool(model.allow_user_memory_structured),
            allow_user_memory_vector=bool(model.allow_user_memory_vector),
            rag_config_id=model.rag_config_id,
            allow_session_context=bool(model.allow_session_context),
            allow_memory_write=bool(model.allow_memory_write),
        )

    async def list_system_node_templates(
        self,
        *,
        tenant_id: UUID,
    ) -> list[NodeTemplateCatalogItem]:
        templates = await self.repository.list_active_system_node_templates()
        return [
            NodeTemplateCatalogItem(
                id=template.node_template_id,
                code=template.code,
                node_type=template.node_type,
                default_config=template.default_config,
            )
            for template in templates
        ]

    async def copy_node_from_template(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        node_template_id: UUID,
        overrides: dict | None,
        allow_rag_tenant: bool,
        allow_user_memory_structured: bool,
        allow_user_memory_vector: bool,
        rag_config_id: UUID | None,
        allow_session_context: bool,
        allow_memory_write: bool,
        principal_id: str,
    ) -> Node:
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")

        template = await self.repository.get_node_template(node_template_id)
        if template is None:
            raise NotFoundServiceException(message="node_template_not_found")
        if not template.is_active:
            raise ResourceBlockedServiceException(message="node_template_not_active")
        if template.scope == "tenant" and template.owner_tenant_id != tenant_id:
            raise ResourceBlockedServiceException(message="node_template_not_available_for_tenant")

        base_config = template.default_config or {}
        effective_overrides = overrides or {}
        effective_config = {**base_config, **effective_overrides}
        validate_node_config(template.node_type, effective_config)
        node_prompt_id = await self.repository.get_active_prompt_id_by_node_type(template.node_type)
        if node_prompt_id is None:
            raise NotFoundServiceException(message="node_prompt_not_found")

        await self._assert_at_most_one_allow_memory_write_on_create(
            flow_version_id=version_uuid,
            allow_memory_write=allow_memory_write,
        )
        node_model = await self.repository.create_node_from_template(
            flow_version_id=version_uuid,
            node_type=template.node_type,
            config=effective_config,
            source_node_template_id=template.node_template_id,
            node_prompt_id=node_prompt_id,
            allow_rag_tenant=allow_rag_tenant,
            allow_user_memory_structured=allow_user_memory_structured,
            allow_user_memory_vector=allow_user_memory_vector,
            rag_config_id=rag_config_id,
            allow_session_context=allow_session_context,
            allow_memory_write=allow_memory_write,
            created_by=principal_id,
        )

        draft = await self.repository.get_flow_graph_draft(version_uuid)
        if draft is None:
            definition = FlowGraphDefinition(
                start_node=str(node_model.node_id),
                nodes={
                    str(node_model.node_id): FlowGraphNodeSpec(
                        type=template.node_type,
                        config=effective_config,
                    )
                },
                edges=[],
            )
        else:
            definition = FlowGraphDefinition.model_validate(draft.definition)
            definition.nodes[str(node_model.node_id)] = FlowGraphNodeSpec(
                type=template.node_type,
                config=effective_config,
            )

        await self.repository.upsert_flow_graph_draft(
            flow_version_id=version_uuid,
            definition=definition.model_dump(),
            principal_id=principal_id,
        )

        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="node",
            resource_id=node_model.node_id,
            version_id=version_uuid,
            event_type="NODE_CREATED_FROM_TEMPLATE",
            change_type="CREATE",
            principal_id=principal_id,
            justification="copy node from template",
            schema_version=1,
        )

        return Node(
            id=node_model.node_id,
            flow_version_id=node_model.flow_version_id,
            node_prompt_id=node_model.node_prompt_id,
            allow_rag_tenant=bool(node_model.allow_rag_tenant),
            allow_user_memory_structured=bool(node_model.allow_user_memory_structured),
            allow_user_memory_vector=bool(node_model.allow_user_memory_vector),
            rag_config_id=node_model.rag_config_id,
            allow_session_context=bool(node_model.allow_session_context),
            allow_memory_write=bool(node_model.allow_memory_write),
        )

    async def copy_node_from_template_request(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        payload: NodeTemplateCopyRequest,
        principal_id: str,
    ) -> Node:
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        if payload.flow_id != flow_uuid or payload.flow_version_id != version_uuid:
            raise DomainValidationException(message="flow_id_or_version_mismatch")
        if payload.node_template_id is None and not payload.code:
            raise DomainValidationException(message="node_template_identifier_required")
        template_id = payload.node_template_id
        if template_id is None and payload.code:
            template = await self.repository.get_active_system_node_template_by_code(
                code=payload.code
            )
            if template is None:
                raise NotFoundServiceException(message="node_template_not_found")
            template_id = template.node_template_id
        if template_id is None:
            raise DomainValidationException(message="node_template_identifier_required")
        return await self.copy_node_from_template(
            tenant_id=tenant_id,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            node_template_id=template_id,
            overrides=payload.overrides,
            allow_rag_tenant=payload.allow_rag_tenant,
            allow_user_memory_structured=payload.allow_user_memory_structured,
            allow_user_memory_vector=payload.allow_user_memory_vector,
            rag_config_id=payload.rag_config_id,
            allow_session_context=payload.allow_session_context,
            allow_memory_write=payload.allow_memory_write,
            principal_id=principal_id,
        )

    async def list_routers(self, *, tenant_id: UUID, limit: int = 200) -> list[Router]:
        routers = await self.repository.list_routers(tenant_id=tenant_id, limit=limit)
        return [Router(id=router.router_id, node_id=router.node_id) for router in routers]

    async def create_router(
        self, *, tenant_id: UUID, router_create: RouterCreate, principal_id: str
    ) -> Router:
        node_model = await self.repository.get_node(router_create.node_id)
        if node_model is None:
            raise NotFoundServiceException(message="node_not_found")
        version = await self.repository.get_flow_version(node_model.flow_version_id)
        if version is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        flow = await self.repository.get_flow(version.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        model = await self.repository.create_router(
            node_id=router_create.node_id, created_by=principal_id
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="router",
            resource_id=model.router_id,
            version_id=None,
            event_type="ROUTER_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create router",
            schema_version=1,
        )
        return Router(id=model.router_id, node_id=model.node_id)

    async def create_condition_expression(
        self,
        *,
        tenant_id: UUID,
        condition_expression_create: ConditionExpressionCreate,
        principal_id: str,
    ) -> ConditionExpression:
        model = await self.repository.create_condition_expression(
            expression=condition_expression_create.expression, created_by=principal_id
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="condition_expression",
            resource_id=model.condition_expression_id,
            version_id=None,
            event_type="CONDITION_EXPRESSION_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create condition expression",
            schema_version=1,
        )
        return ConditionExpression(id=model.condition_expression_id, expression=model.expression)

    async def create_routing_rule(
        self,
        *,
        tenant_id: UUID,
        routing_rule_create: RoutingRuleCreate,
        principal_id: str,
    ) -> RoutingRule:
        router_model = await self.repository.get_router(routing_rule_create.router_id)
        if router_model is None:
            raise NotFoundServiceException(message="router_not_found")
        router_node = await self.repository.get_node(router_model.node_id)
        if router_node is None:
            raise NotFoundServiceException(message="router_node_not_found")
        version = await self.repository.get_flow_version(router_node.flow_version_id)
        if version is None:
            raise NotFoundServiceException(message="flow_version_not_found")
        flow = await self.repository.get_flow(version.flow_id)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        model = await self.repository.create_routing_rule(
            router_id=routing_rule_create.router_id,
            condition_expression_id=routing_rule_create.condition_expression_id,
            from_node_id=routing_rule_create.from_node_id,
            to_node_id=routing_rule_create.to_node_id,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="routing_rule",
            resource_id=model.routing_rule_id,
            version_id=None,
            event_type="ROUTING_RULE_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create routing rule",
            schema_version=1,
        )
        return RoutingRule(
            id=model.routing_rule_id,
            router_id=model.router_id,
            condition_expression_id=model.condition_expression_id,
            from_node_id=model.from_node_id,
            to_node_id=model.to_node_id,
        )

    async def create_custom_node(
        self,
        *,
        tenant_id: UUID,
        flow_id: str,
        flow_version_id: str,
        payload: CustomNodeCreate,
        principal_id: str,
    ) -> Node:
        flow_uuid = UUID(flow_id)
        version_uuid = UUID(flow_version_id)
        if payload.flow_id != flow_uuid or payload.flow_version_id != version_uuid:
            raise DomainValidationException(message="flow_id_or_version_mismatch")
        flow = await self.repository.get_flow(flow_uuid)
        if flow is None or flow.tenant_id != tenant_id:
            raise NotFoundServiceException(message="flow_not_found")
        version = await self.repository.get_flow_version(version_uuid)
        if version is None or version.flow_id != flow_uuid:
            raise NotFoundServiceException(message="flow_version_not_found")
        validate_node_config(payload.node_type, payload.config or {})
        await self._assert_at_most_one_allow_memory_write_on_create(
            flow_version_id=version_uuid,
            allow_memory_write=payload.allow_memory_write,
        )
        node_model = await self.repository.create_custom_node(
            flow_version_id=version_uuid,
            node_type=payload.node_type,
            config=payload.config or {},
            node_prompt_id=payload.node_prompt_id,
            allow_rag_tenant=payload.allow_rag_tenant,
            allow_user_memory_structured=payload.allow_user_memory_structured,
            allow_user_memory_vector=payload.allow_user_memory_vector,
            rag_config_id=payload.rag_config_id,
            allow_session_context=payload.allow_session_context,
            allow_memory_write=payload.allow_memory_write,
            created_by=principal_id,
        )
        draft = await self.repository.get_flow_graph_draft(version_uuid)
        if draft is None:
            definition = FlowGraphDefinition(
                start_node=str(node_model.node_id),
                nodes={
                    str(node_model.node_id): FlowGraphNodeSpec(
                        type=payload.node_type,
                        config=payload.config or {},
                    )
                },
                edges=[],
            )
        else:
            definition = FlowGraphDefinition.model_validate(draft.definition)
            definition.nodes[str(node_model.node_id)] = FlowGraphNodeSpec(
                type=payload.node_type,
                config=payload.config or {},
            )
        await self.repository.upsert_flow_graph_draft(
            flow_version_id=version_uuid,
            definition=definition.model_dump(),
            principal_id=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="node",
            resource_id=node_model.node_id,
            version_id=version_uuid,
            event_type="NODE_CREATED_CUSTOM",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create custom node",
            schema_version=1,
        )
        return Node(
            id=node_model.node_id,
            flow_version_id=node_model.flow_version_id,
            node_prompt_id=node_model.node_prompt_id,
            allow_rag_tenant=bool(node_model.allow_rag_tenant),
            allow_user_memory_structured=bool(node_model.allow_user_memory_structured),
            allow_user_memory_vector=bool(node_model.allow_user_memory_vector),
            rag_config_id=node_model.rag_config_id,
            allow_session_context=bool(node_model.allow_session_context),
            allow_memory_write=bool(node_model.allow_memory_write),
        )
