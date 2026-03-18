from __future__ import annotations

import asyncio
from uuid import UUID

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.governance.services.governance_policies_service import (
    GovernancePoliciesService,
)
from domain.human_sla.repositories.human_sla_policy_repository import (
    HumanSLAPolicyRepository,
)
from domain.rag.repositories.rag_repository import RagRepository
from domain.tenants.repositories.tenant_summary_repository import (
    TenantSummaryRepository,
)
from domain.tenants.schemas.tenant_summary_internal import ToolBindingDetail
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.tenants.schemas.tenant_operational_summary import (
    AgentOperationalSummary,
    AiTaskOperationalSummary,
    CapabilitiesBlock,
    CountsBlock,
    FlowGraphSummary,
    FlowNodeOperational,
    FlowOperational,
    NodeAgentBindingSummary,
    NodeToolBindingSummary,
    PolicyRef,
    RagConfigSummaryItem,
    RagOperationalBlock,
    ResolvedFlowVersionBlock,
    TenantMetricsBlock,
    TenantOperationalSummaryResponse,
    TenantPoliciesOperational,
    ToolCapabilityItem,
)
from domain.ai_policy.services.ai_service import AIService
from domain.tools.repositories.tools_repository import ToolsRepository
from exceptions.service_exceptions import NotFoundServiceException

SUMMARY_AI_POLICIES_LIMIT = 100
SUMMARY_EXEC_LIMIT_POLICIES_LIMIT = 100
SUMMARY_TOOL_CAPABILITIES_LIMIT = 200
SUMMARY_RAG_CONFIGS_LIMIT = 200


def _node_edge_from_definition(payload: object) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    nodes = payload.get("nodes")
    if isinstance(nodes, dict):
        nc = len(nodes)
    elif isinstance(nodes, list):
        nc = len(nodes)
    else:
        nc = 0
    edges = payload.get("edges")
    ec = len(edges) if isinstance(edges, list) else 0
    return nc, ec


def _start_node_from_definition(payload: object) -> UUID | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("start_node")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None


class TenantSummaryService:
    def __init__(
        self,
        tenants_repository: TenantsRepository,
        agents_repository: AgentsRepository,
        governance_policies_service: GovernancePoliciesService,
        tenant_summary_repository: TenantSummaryRepository,
        tools_repository: ToolsRepository | None = None,
        rag_repository: RagRepository | None = None,
        human_sla_policy_repository: HumanSLAPolicyRepository | None = None,
        ai_service: AIService | None = None,
        ai_repository: AIRepository | None = None,
        execution_limit_policy_repository: ExecutionLimitPolicyRepository | None = None,
    ) -> None:
        self.tenants_repository = tenants_repository
        self.agents_repository = agents_repository
        self.governance_policies_service = governance_policies_service
        self.tenant_summary_repository = tenant_summary_repository
        self.tools_repository = tools_repository
        self.rag_repository = rag_repository
        self.human_sla_policy_repository = human_sla_policy_repository
        self.ai_service = ai_service
        self.ai_repository = ai_repository
        self.execution_limit_policy_repository = execution_limit_policy_repository

    async def get_current_summary(
        self, *, tenant_id: UUID
    ) -> TenantOperationalSummaryResponse:
        tenant = await self.tenants_repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")
        tenant_dict = tenant.to_dict()
        tenant_dict["id"] = tenant_dict.pop("tenant_id")

        snap_task = self.tenant_summary_repository.load_operational_snapshot(
            tenant_id=tenant_id
        )
        metrics_task = self.tenant_summary_repository.load_operational_metrics(
            tenant_id=tenant_id
        )
        activation_task = (
            self.tenant_summary_repository.load_policy_activation_sets(
                tenant_id=tenant_id
            )
        )
        gov_gather = asyncio.gather(
            self.governance_policies_service.list_runtime_policies(
                tenant_id=tenant_id
            ),
            self.governance_policies_service.list_access_policies(
                tenant_id=tenant_id
            ),
            self.governance_policies_service.list_rate_limit_policies(
                tenant_id=tenant_id
            ),
            self.governance_policies_service.list_billing_policies(
                tenant_id=tenant_id
            ),
            self.governance_policies_service.list_memory_policies(
                tenant_id=tenant_id
            ),
            self.governance_policies_service.list_rag_policies(
                tenant_id=tenant_id
            ),
        )
        snap, metrics_db, activation, gov_results = await asyncio.gather(
            snap_task, metrics_task, activation_task, gov_gather
        )
        (
            runtime,
            access,
            rate_limit,
            billing,
            memory,
            rag_pol,
        ) = gov_results

        ai_exec_policies: list = []
        if self.ai_repository:
            try:
                ai_exec_policies = await self.ai_repository.list_ai_execution_policies(
                    tenant_id=tenant_id, limit=SUMMARY_AI_POLICIES_LIMIT
                )
            except Exception:
                ai_exec_policies = []

        exec_limit_policies: list = []
        if self.execution_limit_policy_repository:
            try:
                exec_limit_policies = await self.execution_limit_policy_repository.list_policies_for_tenant(
                    tenant_id, limit=SUMMARY_EXEC_LIMIT_POLICIES_LIMIT
                )
            except Exception:
                exec_limit_policies = []

        human_sla_list: list = []
        if self.human_sla_policy_repository:
            try:
                human_sla_list = await self.human_sla_policy_repository.list_by_tenant(
                    tenant_id=tenant_id
                )
            except Exception:
                pass

        policies = TenantPoliciesOperational(
            runtime_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.scope,
                    active=(p.status or "").upper() == "ACTIVE",
                )
                for p in runtime
            ],
            access_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.name,
                    active=p.id in activation.access_published,
                )
                for p in access
            ],
            rate_limit_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.name,
                    active=p.id in activation.rate_limit_published,
                )
                for p in rate_limit
            ],
            billing_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.name,
                    active=p.id in activation.billing_activated,
                )
                for p in billing
            ],
            memory_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.name,
                    active=p.id in activation.memory_activated,
                )
                for p in memory
            ],
            rag_policy=[
                PolicyRef(
                    id=p.id,
                    name=p.name,
                    active=p.id in activation.rag_activated,
                )
                for p in rag_pol
            ],
            ai_execution_policy=[
                PolicyRef(
                    id=p.ai_execution_policy_id,
                    name=(p.description or "")[:256] or None,
                    active=p.ai_execution_policy_id
                    in activation.ai_execution_published,
                )
                for p in ai_exec_policies
            ],
            execution_limit_policy=[
                PolicyRef(
                    id=p.execution_limit_policy_id,
                    name=p.name,
                    active=p.execution_limit_policy_id
                    in activation.execution_limit_published,
                )
                for p in exec_limit_policies
            ],
            human_sla_policy=[
                PolicyRef(
                    id=p.human_sla_policy_id,
                    name=p.name,
                    active=bool(p.active),
                )
                for p in human_sla_list
            ],
        )

        seen_agents: set[UUID] = set()
        agents_out: list[AgentOperationalSummary] = []
        for agent, av in snap.agents_with_active_version:
            if agent.agent_id in seen_agents:
                continue
            seen_agents.add(agent.agent_id)
            av_id = None
            label = None
            aep = None
            rc = None
            st = None
            if av is not None:
                av_id = av.agent_version_id
                label = f"{av.version_major}.{av.version_minor}.{av.version_patch}"
                aep = av.ai_execution_policy_version_id
                rc = av.rag_config_id
                st = str(av.status)
            agents_out.append(
                AgentOperationalSummary(
                    agent_id=agent.agent_id,
                    name=agent.name,
                    agent_version_id=av_id,
                    agent_version_label=label,
                    ai_execution_policy_version_id=aep,
                    rag_config_id=rc,
                    status=st,
                )
            )

        flows_out: list[FlowOperational] = []
        for flow in snap.flows:
            fv = snap.flow_resolved_version.get(flow.flow_id)
            kind = snap.flow_resolution_kind.get(flow.flow_id, "none")
            resolved_block: ResolvedFlowVersionBlock | None = None
            if fv is not None:
                pub_at = (
                    fv.activated_at
                    if kind == "active_flow_version"
                    else fv.created_at
                )
                resolved_block = ResolvedFlowVersionBlock(
                    flow_version_id=fv.flow_version_id,
                    resolution=kind,
                    status=str(fv.status),
                    version=(
                        f"{fv.version_major}.{fv.version_minor}."
                        f"{fv.version_patch}"
                    ),
                    published_at=pub_at,
                )
            graph_model = None
            draft_model = None
            snapshot_model = None
            nodes_db: list = []
            if fv is not None:
                graph_model = snap.graphs_by_flow_version.get(fv.flow_version_id)
                draft_model = snap.drafts_by_flow_version.get(fv.flow_version_id)
                snapshot_model = snap.snapshots_by_flow_version.get(
                    fv.flow_version_id
                )
                nodes_db = snap.nodes_by_flow_version.get(fv.flow_version_id, [])

            canon_def: dict = {}
            if graph_model is not None and isinstance(
                graph_model.definition, dict
            ):
                canon_def = graph_model.definition
            draft_def: dict = {}
            if draft_model is not None and isinstance(
                draft_model.definition, dict
            ):
                draft_def = draft_model.definition
            snap_def: dict = {}
            if snapshot_model is not None and isinstance(
                snapshot_model.snapshot, dict
            ):
                snap_def = snapshot_model.snapshot

            nc_canon, ec_canon = _node_edge_from_definition(canon_def)
            nc_draft, ec_draft = _node_edge_from_definition(draft_def)
            nc_snap, ec_snap = _node_edge_from_definition(snap_def)

            raw_nodes = canon_def.get("nodes") if isinstance(canon_def, dict) else {}
            if not isinstance(raw_nodes, dict):
                raw_nodes = {}
            node_count = len(raw_nodes) if raw_nodes else len(nodes_db)

            if ec_snap > 0 or nc_snap > 0:
                edges_count = ec_snap
                node_count_primary = nc_snap if nc_snap > 0 else node_count
            elif ec_draft > 0 or nc_draft > 0:
                edges_count = ec_draft
                node_count_primary = nc_draft if nc_draft > 0 else node_count
            else:
                edges_count = ec_canon
                node_count_primary = nc_canon if nc_canon > 0 else node_count

            start_node_id = (
                _start_node_from_definition(snap_def)
                or _start_node_from_definition(draft_def)
                or _start_node_from_definition(canon_def)
            )

            flow_nodes_ops: list[FlowNodeOperational] = []
            for n in nodes_db:
                spec = raw_nodes.get(str(n.node_id)) or {}
                if not isinstance(spec, dict):
                    spec = {}
                ntype = (
                    (n.node_type or "").strip()
                    or (spec.get("type") if isinstance(spec.get("type"), str) else None)
                    or "unknown"
                )
                b = snap.binding_by_node_id.get(n.node_id)
                agent_binding = None
                bindings: list[ToolBindingDetail] = []
                if b is not None:
                    agent_binding = NodeAgentBindingSummary(
                        agent_id=b.agent_id,
                        agent_version_id=b.agent_version_id,
                        agent_version_is_active=b.agent_version_is_active,
                    )
                    bindings = snap.tool_bindings_by_agent_version.get(
                        b.agent_version_id, []
                    )
                at = None
                if n.ai_task_id and n.ai_task_id in snap.ai_tasks_by_id:
                    t = snap.ai_tasks_by_id[n.ai_task_id]
                    at = AiTaskOperationalSummary(
                        ai_task_id=t.ai_task_id,
                        name=t.name,
                        allow_rag_tenant=bool(t.allow_rag_tenant),
                        allow_user_memory=bool(t.allow_user_memory),
                        allow_session_context=bool(t.allow_session_context),
                        allow_memory_write=bool(t.allow_memory_write),
                    )
                flow_nodes_ops.append(
                    FlowNodeOperational(
                        node_id=n.node_id,
                        node_type=str(ntype),
                        source_node_template_id=n.source_node_template_id,
                        ai_task=at,
                        agent_binding=agent_binding,
                        tool_bindings=[
                            NodeToolBindingSummary(
                                tool_id=x.tool_id,
                                name=x.name,
                                tool_config_id=x.tool_config_id,
                                status=x.status,
                            )
                            for x in bindings
                        ],
                    )
                )

            graph_present = (
                graph_model is not None
                or draft_model is not None
                or snapshot_model is not None
            )
            flows_out.append(
                FlowOperational(
                    id=flow.flow_id,
                    name=flow.name or "",
                    resolved_flow_version=resolved_block,
                    graph=FlowGraphSummary(
                        present=graph_present,
                        node_count=node_count_primary,
                        edges_count=edges_count,
                        node_count_canonical=nc_canon,
                        edges_count_canonical=ec_canon,
                        node_count_draft=nc_draft,
                        edges_count_draft=ec_draft,
                        node_count_snapshot=nc_snap,
                        edges_count_snapshot=ec_snap,
                        start_node_id=start_node_id,
                    ),
                    nodes=flow_nodes_ops,
                )
            )

        rag_block = RagOperationalBlock()
        try:
            if self.rag_repository:
                rd = await self.rag_repository.get_tenant_rag_summary(
                    tenant_id=tenant_id,
                    configs_limit=SUMMARY_RAG_CONFIGS_LIMIT,
                )
                rag_block = RagOperationalBlock(
                    vector_stores_count=rd.vector_stores_count,
                    documents_count=rd.documents_count,
                    chunks_count=rd.chunks_count,
                    rag_configs_count=rd.rag_configs_count,
                    configs=[
                        RagConfigSummaryItem(
                            vector_store_id=c.vector_store_id,
                            name=c.name,
                            rag_config_id=c.rag_config_id,
                            status=c.status,
                        )
                        for c in rd.configs
                    ],
                )
        except Exception:
            pass

        tools_items: list[ToolCapabilityItem] = []
        try:
            if self.tools_repository:
                rows = await self.tools_repository.list_tool_capabilities_preview(
                    tenant_id=tenant_id,
                    limit=SUMMARY_TOOL_CAPABILITIES_LIMIT,
                )
                tools_items = [
                    ToolCapabilityItem(
                        tool_id=tid,
                        name=name,
                        tool_config_id=tcid,
                        status=st,
                    )
                    for tid, name, tcid, st in rows
                ]
        except Exception:
            pass

        models_count = 0
        try:
            if self.ai_service:
                models_list = await self.ai_service.list_models()
                models_count = len(models_list)
        except Exception:
            pass

        active_av = 0
        try:
            active_av = await self.agents_repository.count_active_agent_versions(
                tenant_id=tenant_id
            )
        except Exception:
            active_av = sum(1 for _, av in snap.agents_with_active_version if av)

        metrics = TenantMetricsBlock(
            sessions=metrics_db.sessions,
            end_users=metrics_db.end_users,
            sla_cases=metrics_db.sla_cases,
            flow_runs=metrics_db.flow_runs,
            interactions=metrics_db.interactions,
            response_artifacts=metrics_db.response_artifacts,
            run_failures=metrics_db.run_failures,
        )

        return TenantOperationalSummaryResponse(
            **tenant_dict,
            agents=agents_out,
            flows=flows_out,
            policies=policies,
            rag=rag_block,
            capabilities=CapabilitiesBlock(
                tools=tools_items,
                models_available_count=models_count,
            ),
            counts=CountsBlock(
                active_agent_versions=active_av,
                published_flow_versions=snap.published_flow_versions_count,
                flows_total=len(snap.flows),
                nodes_total=snap.nodes_total,
                agent_versions_total=snap.agent_versions_total,
            ),
            metrics=metrics,
        )
