from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tenants.schemas.tenant_summary_internal import (
    NodeBindingRow,
    PolicyActivationSets,
    TenantOperationalDbSnapshot,
    TenantOperationalMetrics,
    ToolBindingDetail,
)

_POLICY_ACTIVATION_EMPTY = PolicyActivationSets(
    access_published=frozenset(),
    rate_limit_published=frozenset(),
    billing_activated=frozenset(),
    memory_activated=frozenset(),
    rag_activated=frozenset(),
    ai_execution_published=frozenset(),
    execution_limit_published=frozenset(),
)
from domain.tenants.services.tenant_summary_service import TenantSummaryService
from exceptions.service_exceptions import NotFoundServiceException


@pytest.mark.asyncio
async def test_get_current_summary_structure() -> None:
    tenant_id = uuid4()
    flow_id = uuid4()
    fv_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    av_id = uuid4()
    tool_id = uuid4()
    tc_id = uuid4()

    tenant_row = MagicMock()
    tenant_row.to_dict.return_value = {
        "tenant_id": tenant_id,
        "name": "T",
        "description": None,
        "timezone": "America/Sao_Paulo",
        "is_active": True,
        "currency": "BRL",
        "language": "pt_BR",
        "external_id": None,
        "contact_name": None,
        "contact_phone": None,
        "settings": None,
    }

    flow = SimpleNamespace(flow_id=flow_id, name="flow-a")
    fv = SimpleNamespace(
        flow_version_id=fv_id,
        flow_id=flow_id,
        status="PUBLISHED",
        version_major=1,
        version_minor=0,
        version_patch=0,
        activated_at=None,
        created_at=datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
        is_active=False,
    )
    graph_def = {
        "nodes": {
            str(node_id): {"type": "intent"},
        },
        "edges": [],
        "start_node": str(node_id),
    }
    graph = SimpleNamespace(flow_version_id=fv_id, definition=graph_def)
    snap_payload = {
        "nodes": {str(node_id): {}},
        "edges": [{"from_node": str(node_id), "to_node": str(uuid4())}],
        "start_node": str(node_id),
        "schema_version": 1,
    }
    snapshot = SimpleNamespace(flow_version_id=fv_id, snapshot=snap_payload)
    node = SimpleNamespace(
        node_id=node_id,
        flow_version_id=fv_id,
        ai_task_id=None,
        node_type="llm",
        source_node_template_id=None,
    )
    av = SimpleNamespace(
        agent_version_id=av_id,
        agent_id=agent_id,
        version_major=1,
        version_minor=0,
        version_patch=0,
        is_active=True,
        status="PUBLISHED",
        ai_execution_policy_version_id=uuid4(),
        rag_config_id=uuid4(),
    )
    agent = SimpleNamespace(agent_id=agent_id, name="Agent")

    snap = TenantOperationalDbSnapshot(
        flows=[flow],
        flow_resolved_version={flow_id: fv},
        flow_resolution_kind={flow_id: "latest_published"},
        graphs_by_flow_version={fv_id: graph},
        drafts_by_flow_version={},
        snapshots_by_flow_version={fv_id: snapshot},
        nodes_by_flow_version={fv_id: [node]},
        binding_by_node_id={
            node_id: NodeBindingRow(
                agent_id=agent_id,
                agent_version_id=av_id,
                agent_version_is_active=True,
            )
        },
        ai_tasks_by_id={},
        tool_bindings_by_agent_version={
            av_id: [
                ToolBindingDetail(
                    tool_id=tool_id,
                    name="t1",
                    tool_config_id=tc_id,
                    status="PUBLISHED",
                )
            ]
        },
        agents_with_active_version=[(agent, av)],
        published_flow_versions_count=3,
        nodes_total=5,
        agent_versions_total=2,
    )

    metrics = TenantOperationalMetrics(
        sessions=1,
        end_users=2,
        sla_cases=0,
        flow_runs=3,
        interactions=4,
        response_artifacts=5,
        run_failures=0,
    )

    tenants_repo = AsyncMock()
    tenants_repo.get_tenant = AsyncMock(return_value=tenant_row)
    summary_repo = AsyncMock()
    summary_repo.load_operational_snapshot = AsyncMock(return_value=snap)
    summary_repo.load_operational_metrics = AsyncMock(return_value=metrics)
    summary_repo.load_policy_activation_sets = AsyncMock(
        return_value=_POLICY_ACTIVATION_EMPTY
    )
    gov = AsyncMock()
    gov.list_runtime_policies = AsyncMock(return_value=[])
    gov.list_access_policies = AsyncMock(return_value=[])
    gov.list_rate_limit_policies = AsyncMock(return_value=[])
    gov.list_billing_policies = AsyncMock(return_value=[])
    gov.list_memory_policies = AsyncMock(return_value=[])
    gov.list_rag_policies = AsyncMock(return_value=[])

    ai_repo = AsyncMock()
    ai_repo.list_ai_execution_policies = AsyncMock(return_value=[])
    exec_repo = AsyncMock()
    exec_repo.list_policies_for_tenant = AsyncMock(return_value=[])

    service = TenantSummaryService(
        tenants_repository=tenants_repo,
        agents_repository=AsyncMock(
            count_active_agent_versions=AsyncMock(return_value=1)
        ),
        governance_policies_service=gov,
        tenant_summary_repository=summary_repo,
        tools_repository=None,
        rag_repository=None,
        human_sla_policy_repository=None,
        ai_service=None,
        ai_repository=ai_repo,
        execution_limit_policy_repository=exec_repo,
    )

    out = await service.get_current_summary(tenant_id=tenant_id)

    assert out.id == tenant_id
    assert len(out.agents) == 1
    assert out.agents[0].agent_id == agent_id
    assert out.agents[0].agent_version_label == "1.0.0"
    assert out.agents[0].status == "PUBLISHED"
    assert len(out.flows) == 1
    assert out.flows[0].resolved_flow_version is not None
    assert out.flows[0].resolved_flow_version.resolution == "latest_published"
    assert out.flows[0].graph.present is True
    assert out.flows[0].graph.edges_count_snapshot == 1
    assert out.flows[0].graph.edges_count == 1
    assert out.flows[0].graph.start_node_id == node_id
    assert len(out.flows[0].nodes) == 1
    assert out.flows[0].nodes[0].node_type == "llm"
    assert len(out.flows[0].nodes[0].tool_bindings) == 1
    assert out.flows[0].nodes[0].tool_bindings[0].tool_id == tool_id
    assert out.counts.published_flow_versions == 3
    assert out.counts.flows_total == 1
    assert out.counts.nodes_total == 5
    assert out.counts.agent_versions_total == 2
    assert out.metrics.sessions == 1
    assert out.policies.ai_execution_policy == []
    assert out.policies.execution_limit_policy == []


@pytest.mark.asyncio
async def test_node_type_fallback_from_graph_definition() -> None:
    tenant_id = uuid4()
    flow_id = uuid4()
    fv_id = uuid4()
    node_id = uuid4()

    tenant_row = MagicMock()
    tenant_row.to_dict.return_value = {
        "tenant_id": tenant_id,
        "name": "T",
        "description": None,
        "timezone": "UTC",
        "is_active": True,
        "currency": "USD",
        "language": "en",
        "external_id": None,
        "contact_name": None,
        "contact_phone": None,
        "settings": None,
    }
    flow = SimpleNamespace(flow_id=flow_id, name="f")
    fv = SimpleNamespace(
        flow_version_id=fv_id,
        flow_id=flow_id,
        status="PUBLISHED",
        version_major=1,
        version_minor=0,
        version_patch=0,
        activated_at=None,
        created_at=datetime.now(tz=timezone.utc),
        is_active=True,
    )
    graph_def = {
        "nodes": {str(node_id): {"type": "router"}},
        "edges": [],
        "start_node": str(node_id),
    }
    graph = SimpleNamespace(flow_version_id=fv_id, definition=graph_def)
    node = SimpleNamespace(
        node_id=node_id,
        flow_version_id=fv_id,
        ai_task_id=None,
        node_type=None,
        source_node_template_id=None,
    )
    snap = TenantOperationalDbSnapshot(
        flows=[flow],
        flow_resolved_version={flow_id: fv},
        flow_resolution_kind={flow_id: "active_flow_version"},
        graphs_by_flow_version={fv_id: graph},
        nodes_by_flow_version={fv_id: [node]},
        agents_with_active_version=[],
        published_flow_versions_count=1,
    )
    summary_repo = AsyncMock()
    summary_repo.load_operational_snapshot = AsyncMock(return_value=snap)
    summary_repo.load_operational_metrics = AsyncMock(
        return_value=TenantOperationalMetrics()
    )
    summary_repo.load_policy_activation_sets = AsyncMock(
        return_value=_POLICY_ACTIVATION_EMPTY
    )
    gov = AsyncMock()
    for m in (
        "list_runtime_policies",
        "list_access_policies",
        "list_rate_limit_policies",
        "list_billing_policies",
        "list_memory_policies",
        "list_rag_policies",
    ):
        setattr(gov, m, AsyncMock(return_value=[]))

    service = TenantSummaryService(
        tenants_repository=AsyncMock(get_tenant=AsyncMock(return_value=tenant_row)),
        agents_repository=AsyncMock(
            count_active_agent_versions=AsyncMock(return_value=0)
        ),
        governance_policies_service=gov,
        tenant_summary_repository=summary_repo,
        ai_repository=AsyncMock(list_ai_execution_policies=AsyncMock(return_value=[])),
        execution_limit_policy_repository=AsyncMock(
            list_policies_for_tenant=AsyncMock(return_value=[])
        ),
    )
    out = await service.get_current_summary(tenant_id=tenant_id)
    assert out.flows[0].nodes[0].node_type == "router"


@pytest.mark.asyncio
async def test_draft_edges_when_no_snapshot() -> None:
    tenant_id = uuid4()
    flow_id = uuid4()
    fv_id = uuid4()
    node_id = uuid4()

    tenant_row = MagicMock()
    tenant_row.to_dict.return_value = {
        "tenant_id": tenant_id,
        "name": "T",
        "description": None,
        "timezone": "UTC",
        "is_active": True,
        "currency": "USD",
        "language": "en",
        "external_id": None,
        "contact_name": None,
        "contact_phone": None,
        "settings": None,
    }
    flow = SimpleNamespace(flow_id=flow_id, name="f")
    fv = SimpleNamespace(
        flow_version_id=fv_id,
        flow_id=flow_id,
        status="DRAFT",
        version_major=1,
        version_minor=0,
        version_patch=0,
        activated_at=None,
        created_at=datetime.now(tz=timezone.utc),
        is_active=True,
    )
    graph = SimpleNamespace(
        flow_version_id=fv_id,
        definition={"nodes": {}, "edges": [], "start_node": str(node_id)},
    )
    draft = SimpleNamespace(
        flow_version_id=fv_id,
        definition={
            "nodes": {str(node_id): {"type": "x"}},
            "edges": [{"a": 1}, {"b": 2}],
            "start_node": str(node_id),
        },
    )
    node = SimpleNamespace(
        node_id=node_id,
        flow_version_id=fv_id,
        ai_task_id=None,
        node_type="x",
        source_node_template_id=None,
    )
    snap = TenantOperationalDbSnapshot(
        flows=[flow],
        flow_resolved_version={flow_id: fv},
        flow_resolution_kind={flow_id: "active_flow_version"},
        graphs_by_flow_version={fv_id: graph},
        drafts_by_flow_version={fv_id: draft},
        nodes_by_flow_version={fv_id: [node]},
        agents_with_active_version=[],
        published_flow_versions_count=0,
    )
    summary_repo = AsyncMock()
    summary_repo.load_operational_snapshot = AsyncMock(return_value=snap)
    summary_repo.load_operational_metrics = AsyncMock(
        return_value=TenantOperationalMetrics()
    )
    summary_repo.load_policy_activation_sets = AsyncMock(
        return_value=_POLICY_ACTIVATION_EMPTY
    )
    gov = AsyncMock()
    for m in (
        "list_runtime_policies",
        "list_access_policies",
        "list_rate_limit_policies",
        "list_billing_policies",
        "list_memory_policies",
        "list_rag_policies",
    ):
        setattr(gov, m, AsyncMock(return_value=[]))

    service = TenantSummaryService(
        tenants_repository=AsyncMock(get_tenant=AsyncMock(return_value=tenant_row)),
        agents_repository=AsyncMock(
            count_active_agent_versions=AsyncMock(return_value=0)
        ),
        governance_policies_service=gov,
        tenant_summary_repository=summary_repo,
        ai_repository=AsyncMock(list_ai_execution_policies=AsyncMock(return_value=[])),
        execution_limit_policy_repository=AsyncMock(
            list_policies_for_tenant=AsyncMock(return_value=[])
        ),
    )
    out = await service.get_current_summary(tenant_id=tenant_id)
    assert out.flows[0].graph.edges_count_draft == 2
    assert out.flows[0].graph.edges_count == 2


@pytest.mark.asyncio
async def test_get_current_summary_tenant_not_found() -> None:
    tenants_repo = AsyncMock()
    tenants_repo.get_tenant = AsyncMock(return_value=None)
    service = TenantSummaryService(
        tenants_repository=tenants_repo,
        agents_repository=AsyncMock(),
        governance_policies_service=AsyncMock(),
        tenant_summary_repository=AsyncMock(),
    )
    with pytest.raises(NotFoundServiceException):
        await service.get_current_summary(tenant_id=uuid4())
