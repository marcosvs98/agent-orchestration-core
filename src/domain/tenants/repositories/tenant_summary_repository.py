from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import and_, func, select

from domain.common.schemas.versioning import VersionStatus
from infra.database import DatabaseConnection
from infra.database.models.agent.agent import Agent as AgentModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.agent.node_agent_binding import (
    NodeAgentBinding as NodeAgentBindingModel,
)
from infra.database.models.conversation.interaction import (
    Interaction as InteractionModel,
)
from infra.database.models.conversation.response_artifact import (
    ResponseArtifact as ResponseArtifactModel,
)
from infra.database.models.conversation.session import Session as SessionModel
from infra.database.models.conversation.user import User as EndUserModel
from infra.database.models.escalation.sla_case import SLACase as SLACaseModel
from infra.database.models.execution.flow_run import FlowRun as FlowRunModel
from infra.database.models.execution.run_failure import RunFailure as RunFailureModel
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel
from infra.database.models.flow.flow_graph_draft import (
    FlowGraphDraft as FlowGraphDraftModel,
)
from infra.database.models.flow.flow_graph_snapshot import (
    FlowGraphSnapshot as FlowGraphSnapshotModel,
)
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.governance.access_policy import (
    AccessPolicy as AccessPolicyModel,
)
from infra.database.models.governance.access_policy_version import (
    AccessPolicyVersion as AccessPolicyVersionModel,
)
from infra.database.models.governance.billing_policy_version import (
    BillingPolicyVersion as BillingPolicyVersionModel,
)
from infra.database.models.governance.execution_limit_policy import (
    ExecutionLimitPolicy as ExecutionLimitPolicyModel,
)
from infra.database.models.governance.execution_limit_policy_version import (
    ExecutionLimitPolicyVersion as ExecutionLimitPolicyVersionModel,
)
from infra.database.models.governance.memory_policy_version import (
    MemoryPolicyVersion as MemoryPolicyVersionModel,
)
from infra.database.models.governance.rag_policy_version import (
    RagPolicyVersion as RagPolicyVersionModel,
)
from infra.database.models.governance.rate_limit_policy import (
    RateLimitPolicy as RateLimitPolicyModel,
)
from infra.database.models.governance.rate_limit_policy_version import (
    RateLimitPolicyVersion as RateLimitPolicyVersionModel,
)
from infra.database.models.ai_policy.execution_policy import (
    AIExecutionPolicy as AIExecutionPolicyModel,
)
from infra.database.models.ai_policy.execution_policy_version import (
    AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
)
from infra.database.models.tool.agent_version_tool_binding import (
    AgentVersionToolBinding as AgentVersionToolBindingModel,
)
from infra.database.models.tool.tool import Tool as ToolModel
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel
from domain.tenants.schemas.tenant_summary_internal import (
    NodeBindingRow,
    PolicyActivationSets,
    TenantOperationalDbSnapshot,
    TenantOperationalMetrics,
    ToolBindingDetail,
)

FLOWS_LIMIT = 50
AGENTS_LIMIT = 200


def _semver_tuple(fv: FlowVersionModel) -> tuple[int, int, int]:
    return (fv.version_major, fv.version_minor, fv.version_patch)


def _pick_best_published(rows: list[FlowVersionModel]) -> FlowVersionModel | None:
    if not rows:
        return None
    best = rows[0]
    for fv in rows[1:]:
        if _semver_tuple(fv) > _semver_tuple(best):
            best = fv
    return best


def _node_and_edge_counts(payload: object) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    nodes = payload.get("nodes")
    if isinstance(nodes, dict):
        node_count = len(nodes)
    elif isinstance(nodes, list):
        node_count = len(nodes)
    else:
        node_count = 0
    edges = payload.get("edges")
    if isinstance(edges, list):
        edge_count = len(edges)
    else:
        edge_count = 0
    return node_count, edge_count


class TenantSummaryRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def load_policy_activation_sets(
        self, *, tenant_id: UUID
    ) -> PolicyActivationSets:
        async with self.db.get_session() as session:
            acc = await session.execute(
                select(AccessPolicyVersionModel.access_policy_id)
                .join(
                    AccessPolicyModel,
                    AccessPolicyModel.access_policy_id
                    == AccessPolicyVersionModel.access_policy_id,
                )
                .where(
                    AccessPolicyModel.tenant_id == tenant_id,
                    AccessPolicyVersionModel.status == VersionStatus.PUBLISHED,
                )
            )
            rl = await session.execute(
                select(RateLimitPolicyVersionModel.rate_limit_policy_id)
                .join(
                    RateLimitPolicyModel,
                    RateLimitPolicyModel.rate_limit_policy_id
                    == RateLimitPolicyVersionModel.rate_limit_policy_id,
                )
                .where(
                    RateLimitPolicyModel.tenant_id == tenant_id,
                    RateLimitPolicyVersionModel.status == VersionStatus.PUBLISHED,
                )
            )
            bill = await session.execute(
                select(BillingPolicyVersionModel.billing_policy_id).where(
                    BillingPolicyVersionModel.tenant_id == tenant_id,
                    BillingPolicyVersionModel.is_active.is_(True),
                )
            )
            mem = await session.execute(
                select(MemoryPolicyVersionModel.memory_policy_id).where(
                    MemoryPolicyVersionModel.tenant_id == tenant_id,
                    MemoryPolicyVersionModel.is_active.is_(True),
                )
            )
            rag = await session.execute(
                select(RagPolicyVersionModel.rag_policy_id).where(
                    RagPolicyVersionModel.tenant_id == tenant_id,
                    RagPolicyVersionModel.is_active.is_(True),
                )
            )
            aie = await session.execute(
                select(AIExecutionPolicyVersionModel.ai_execution_policy_id)
                .join(
                    AIExecutionPolicyModel,
                    AIExecutionPolicyModel.ai_execution_policy_id
                    == AIExecutionPolicyVersionModel.ai_execution_policy_id,
                )
                .where(
                    AIExecutionPolicyModel.tenant_id == tenant_id,
                    AIExecutionPolicyVersionModel.status == VersionStatus.PUBLISHED,
                )
            )
            el = await session.execute(
                select(ExecutionLimitPolicyVersionModel.execution_limit_policy_id)
                .join(
                    ExecutionLimitPolicyModel,
                    ExecutionLimitPolicyModel.execution_limit_policy_id
                    == ExecutionLimitPolicyVersionModel.execution_limit_policy_id,
                )
                .where(
                    ExecutionLimitPolicyModel.tenant_id == tenant_id,
                    ExecutionLimitPolicyVersionModel.status == VersionStatus.PUBLISHED,
                )
            )
            return PolicyActivationSets(
                access_published=frozenset(r[0] for r in acc.all()),
                rate_limit_published=frozenset(r[0] for r in rl.all()),
                billing_activated=frozenset(r[0] for r in bill.all()),
                memory_activated=frozenset(r[0] for r in mem.all()),
                rag_activated=frozenset(r[0] for r in rag.all()),
                ai_execution_published=frozenset(r[0] for r in aie.all()),
                execution_limit_published=frozenset(r[0] for r in el.all()),
            )

    async def load_operational_metrics(
        self, *, tenant_id: UUID
    ) -> TenantOperationalMetrics:
        async with self.db.get_session() as session:
            sessions_q = await session.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.tenant_id == tenant_id)
            )
            end_users_q = await session.execute(
                select(func.count())
                .select_from(EndUserModel)
                .where(EndUserModel.tenant_id == tenant_id)
            )
            sla_q = await session.execute(
                select(func.count())
                .select_from(SLACaseModel)
                .where(SLACaseModel.tenant_id == tenant_id)
            )
            flow_runs_q = await session.execute(
                select(func.count())
                .select_from(FlowRunModel)
                .join(
                    SessionModel,
                    FlowRunModel.session_id == SessionModel.session_id,
                )
                .where(SessionModel.tenant_id == tenant_id)
            )
            interactions_q = await session.execute(
                select(func.count())
                .select_from(InteractionModel)
                .join(
                    SessionModel,
                    InteractionModel.session_id == SessionModel.session_id,
                )
                .where(SessionModel.tenant_id == tenant_id)
            )
            artifacts_q = await session.execute(
                select(func.count())
                .select_from(ResponseArtifactModel)
                .join(
                    InteractionModel,
                    ResponseArtifactModel.interaction_id
                    == InteractionModel.interaction_id,
                )
                .join(
                    SessionModel,
                    InteractionModel.session_id == SessionModel.session_id,
                )
                .where(SessionModel.tenant_id == tenant_id)
            )
            failures_q = await session.execute(
                select(func.count())
                .select_from(RunFailureModel)
                .join(
                    FlowRunModel,
                    RunFailureModel.flow_run_id == FlowRunModel.flow_run_id,
                )
                .join(
                    SessionModel,
                    FlowRunModel.session_id == SessionModel.session_id,
                )
                .where(
                    SessionModel.tenant_id == tenant_id,
                    RunFailureModel.flow_run_id.isnot(None),
                )
            )
            return TenantOperationalMetrics(
                sessions=int(sessions_q.scalar() or 0),
                end_users=int(end_users_q.scalar() or 0),
                sla_cases=int(sla_q.scalar() or 0),
                flow_runs=int(flow_runs_q.scalar() or 0),
                interactions=int(interactions_q.scalar() or 0),
                response_artifacts=int(artifacts_q.scalar() or 0),
                run_failures=int(failures_q.scalar() or 0),
            )

    async def _aggregate_tenant_counts(
        self, session, tenant_id: UUID
    ) -> tuple[int, int]:
        nodes_q = await session.execute(
            select(func.count())
            .select_from(NodeModel)
            .join(
                FlowVersionModel,
                NodeModel.flow_version_id == FlowVersionModel.flow_version_id,
            )
            .join(FlowModel, FlowVersionModel.flow_id == FlowModel.flow_id)
            .where(FlowModel.tenant_id == tenant_id)
        )
        av_q = await session.execute(
            select(func.count())
            .select_from(AgentVersionModel)
            .join(AgentModel, AgentVersionModel.agent_id == AgentModel.agent_id)
            .where(AgentModel.tenant_id == tenant_id)
        )
        return int(nodes_q.scalar() or 0), int(av_q.scalar() or 0)

    async def load_operational_snapshot(
        self, *, tenant_id: UUID
    ) -> TenantOperationalDbSnapshot:
        async with self.db.get_session() as session:
            nodes_total, agent_versions_total = await self._aggregate_tenant_counts(
                session, tenant_id
            )
            flows_result = await session.execute(
                select(FlowModel)
                .where(FlowModel.tenant_id == tenant_id)
                .order_by(FlowModel.created_at.desc())
                .limit(FLOWS_LIMIT)
            )
            flows = list(flows_result.scalars().all())
            if not flows:
                pub_cnt = await session.execute(
                    select(func.count())
                    .select_from(FlowVersionModel)
                    .join(FlowModel, FlowVersionModel.flow_id == FlowModel.flow_id)
                    .where(
                        FlowModel.tenant_id == tenant_id,
                        FlowVersionModel.status == "PUBLISHED",
                    )
                )
                agents_rows = await session.execute(
                    select(AgentModel, AgentVersionModel)
                    .outerjoin(
                        AgentVersionModel,
                        and_(
                            AgentModel.agent_id == AgentVersionModel.agent_id,
                            AgentVersionModel.is_active.is_(True),
                        ),
                    )
                    .where(AgentModel.tenant_id == tenant_id)
                    .limit(AGENTS_LIMIT)
                )
                agents_list = list(agents_rows.all())
                return TenantOperationalDbSnapshot(
                    flows=[],
                    published_flow_versions_count=int(pub_cnt.scalar() or 0),
                    agents_with_active_version=agents_list,
                    nodes_total=nodes_total,
                    agent_versions_total=agent_versions_total,
                )

            flow_ids = [f.flow_id for f in flows]

            active_res = await session.execute(
                select(FlowVersionModel).where(
                    FlowVersionModel.flow_id.in_(flow_ids),
                    FlowVersionModel.is_active.is_(True),
                )
            )
            active_by_flow: dict[UUID, FlowVersionModel] = {}
            for fv in active_res.scalars().all():
                active_by_flow[fv.flow_id] = fv

            missing = [fid for fid in flow_ids if fid not in active_by_flow]
            published_by_flow: dict[UUID, FlowVersionModel] = {}
            if missing:
                pub_res = await session.execute(
                    select(FlowVersionModel).where(
                        FlowVersionModel.flow_id.in_(missing),
                        FlowVersionModel.status == "PUBLISHED",
                    )
                )
                grouped: dict[UUID, list[FlowVersionModel]] = defaultdict(list)
                for fv in pub_res.scalars().all():
                    grouped[fv.flow_id].append(fv)
                for fid, vers in grouped.items():
                    chosen = _pick_best_published(vers)
                    if chosen:
                        published_by_flow[fid] = chosen

            flow_resolved: dict[UUID, FlowVersionModel | None] = {}
            flow_resolution_kind: dict[UUID, str] = {}
            for fid in flow_ids:
                if fid in active_by_flow:
                    flow_resolved[fid] = active_by_flow[fid]
                    flow_resolution_kind[fid] = "active_flow_version"
                elif fid in published_by_flow:
                    flow_resolved[fid] = published_by_flow[fid]
                    flow_resolution_kind[fid] = "latest_published"
                else:
                    flow_resolved[fid] = None
                    flow_resolution_kind[fid] = "none"

            fv_ids = [
                fv.flow_version_id for fv in flow_resolved.values() if fv is not None
            ]

            graphs_by_fv: dict[UUID, FlowGraphModel] = {}
            drafts_by_fv: dict[UUID, FlowGraphDraftModel] = {}
            snapshots_by_fv: dict[UUID, FlowGraphSnapshotModel] = {}
            nodes_by_fv: dict[UUID, list[NodeModel]] = defaultdict(list)
            if fv_ids:
                gres = await session.execute(
                    select(FlowGraphModel).where(
                        FlowGraphModel.flow_version_id.in_(fv_ids)
                    )
                )
                for g in gres.scalars().all():
                    graphs_by_fv[g.flow_version_id] = g

                dres = await session.execute(
                    select(FlowGraphDraftModel).where(
                        FlowGraphDraftModel.flow_version_id.in_(fv_ids)
                    )
                )
                for d in dres.scalars().all():
                    drafts_by_fv[d.flow_version_id] = d

                sres = await session.execute(
                    select(FlowGraphSnapshotModel).where(
                        FlowGraphSnapshotModel.flow_version_id.in_(fv_ids)
                    )
                )
                for s in sres.scalars().all():
                    snapshots_by_fv[s.flow_version_id] = s

                nres = await session.execute(
                    select(NodeModel).where(NodeModel.flow_version_id.in_(fv_ids))
                )
                for n in nres.scalars().all():
                    nodes_by_fv[n.flow_version_id].append(n)

            all_node_ids = [n.node_id for nodes in nodes_by_fv.values() for n in nodes]
            binding_by_node: dict[UUID, NodeBindingRow] = {}
            av_ids_for_tools: set[UUID] = set()
            if all_node_ids:
                bres = await session.execute(
                    select(NodeAgentBindingModel, AgentVersionModel)
                    .join(
                        AgentVersionModel,
                        NodeAgentBindingModel.agent_version_id
                        == AgentVersionModel.agent_version_id,
                    )
                    .where(NodeAgentBindingModel.node_id.in_(all_node_ids))
                )
                for nab, av in bres.all():
                    binding_by_node[nab.node_id] = NodeBindingRow(
                        agent_id=av.agent_id,
                        agent_version_id=av.agent_version_id,
                        agent_version_is_active=bool(av.is_active),
                    )
                    av_ids_for_tools.add(av.agent_version_id)

            tool_bindings_map: dict[UUID, list[ToolBindingDetail]] = defaultdict(list)
            if av_ids_for_tools:
                tb_res = await session.execute(
                    select(
                        AgentVersionToolBindingModel.agent_version_id,
                        ToolModel.tool_id,
                        ToolModel.name,
                        ToolConfigModel.tool_config_id,
                        ToolConfigModel.status,
                    )
                    .join(
                        ToolConfigModel,
                        AgentVersionToolBindingModel.tool_config_id
                        == ToolConfigModel.tool_config_id,
                    )
                    .join(ToolModel, ToolConfigModel.tool_id == ToolModel.tool_id)
                    .where(
                        AgentVersionToolBindingModel.agent_version_id.in_(
                            av_ids_for_tools
                        ),
                        ToolConfigModel.tenant_id == tenant_id,
                    )
                )
                for av_id, tid, tname, tcid, st in tb_res.all():
                    tool_bindings_map[av_id].append(
                        ToolBindingDetail(
                            tool_id=tid,
                            name=tname,
                            tool_config_id=tcid,
                            status=str(st),
                        )
                    )

            pub_cnt = await session.execute(
                select(func.count())
                .select_from(FlowVersionModel)
                .join(FlowModel, FlowVersionModel.flow_id == FlowModel.flow_id)
                .where(
                    FlowModel.tenant_id == tenant_id,
                    FlowVersionModel.status == "PUBLISHED",
                )
            )

            agents_rows = await session.execute(
                select(AgentModel, AgentVersionModel)
                .outerjoin(
                    AgentVersionModel,
                    and_(
                        AgentModel.agent_id == AgentVersionModel.agent_id,
                        AgentVersionModel.is_active.is_(True),
                    ),
                )
                .where(AgentModel.tenant_id == tenant_id)
                .limit(AGENTS_LIMIT)
            )
            agents_list = list(agents_rows.all())

            return TenantOperationalDbSnapshot(
                flows=flows,
                flow_resolved_version=flow_resolved,
                flow_resolution_kind=flow_resolution_kind,
                graphs_by_flow_version=graphs_by_fv,
                drafts_by_flow_version=drafts_by_fv,
                snapshots_by_flow_version=snapshots_by_fv,
                nodes_by_flow_version=dict(nodes_by_fv),
                binding_by_node_id=binding_by_node,
                tool_bindings_by_agent_version=dict(tool_bindings_map),
                agents_with_active_version=agents_list,
                published_flow_versions_count=int(pub_cnt.scalar() or 0),
                nodes_total=nodes_total,
                agent_versions_total=agent_versions_total,
            )
