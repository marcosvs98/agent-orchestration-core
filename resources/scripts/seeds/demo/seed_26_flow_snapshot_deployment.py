from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.governance.schemas.runtime_policy import RuntimePolicyDefinition
from infra.database import get_db
from infra.database.models.flow.flow_deployment import FlowDeployment
from infra.database.models.flow.flow_graph_snapshot import FlowGraphSnapshot
from infra.database.models.flow.flow_snapshot import FlowSnapshot
from infra.database.models.flow.snapshot_binding import SnapshotBinding
from infra.database.models.flow.snapshot_effective_policy import SnapshotEffectivePolicy

from infra.database.models.governance.tenant import Tenant

from seeds.demo.ids import (
    FLOW_DEPLOYMENT_DEFAULT_ID,
    FLOW_DEMO_ID,
    FLOW_GRAPH_SNAPSHOT_ID,
    FLOW_SNAPSHOT_V1_ID,
    FLOW_VERSION_V1_ID,
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
)


def _hash_dict(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


def _flow_snapshot_runtime_policy() -> dict[str, object]:
    raw = {
        "memory_extraction": {
            "enabled": True,
            "rag_config_id": str(RAG_CONFIG_DEMO_ID),
            "preference_schema_id": "user.preference.v1",
            "profile_schema_id": "user.profile_signal.v1",
            "llm": {
                "provider": "OPENAI",
                "model_alias": "gpt-4o-mini",
                "prompt": "Extract user preferences from flow output.",
                "task_type": "MEMORY_EXTRACTION",
            },
        },
    }
    return RuntimePolicyDefinition.model_validate(raw).model_dump(mode="json")


async def seed_flow_snapshot_deployment() -> None:
    async with get_db() as session:
        graph_snapshot_result = await session.execute(
            select(FlowGraphSnapshot).where(
                FlowGraphSnapshot.flow_graph_snapshot_id == FLOW_GRAPH_SNAPSHOT_ID
            )
        )
        graph_snapshot = graph_snapshot_result.scalar_one_or_none()
        if graph_snapshot is None:
            return
        runtime_policy = _flow_snapshot_runtime_policy()
        tool_catalog = {}
        binding_rows: list[dict[str, object]] = []
        payload = {
            "flow_graph_snapshot_id": str(graph_snapshot.flow_graph_snapshot_id),
            "graph_hash": graph_snapshot.graph_hash,
            "graph": graph_snapshot.snapshot,
        }
        snapshot_hash = _hash_dict(
            {
                "graph_hash": graph_snapshot.graph_hash,
                "runtime_policy": runtime_policy,
                "tool_catalog": tool_catalog,
                "bindings": binding_rows,
            }
        )
        flow_snapshot_result = await session.execute(
            select(FlowSnapshot).where(FlowSnapshot.flow_snapshot_id == FLOW_SNAPSHOT_V1_ID)
        )
        flow_snapshot = flow_snapshot_result.scalar_one_or_none()
        if flow_snapshot is None:
            flow_snapshot = FlowSnapshot(
                flow_snapshot_id=FLOW_SNAPSHOT_V1_ID,
                flow_version_id=FLOW_VERSION_V1_ID,
                snapshot_schema_version=1,
                snapshot_hash=snapshot_hash,
                snapshot=payload,
                runtime_policy=runtime_policy,
                tool_catalog=tool_catalog,
                llm_provider_config_hash=None,
                created_by="system",
            )
            session.add(flow_snapshot)
        else:
            flow_snapshot.flow_version_id = FLOW_VERSION_V1_ID
            flow_snapshot.snapshot_schema_version = 1
            flow_snapshot.snapshot_hash = snapshot_hash
            flow_snapshot.snapshot = payload
            flow_snapshot.runtime_policy = runtime_policy
            flow_snapshot.tool_catalog = tool_catalog
            flow_snapshot.created_by = "system"
            session.add(flow_snapshot)
        policy_result = await session.execute(
            select(SnapshotEffectivePolicy).where(
                SnapshotEffectivePolicy.flow_snapshot_id == FLOW_SNAPSHOT_V1_ID
            )
        )
        policy = policy_result.scalar_one_or_none()
        if policy is None:
            session.add(
                SnapshotEffectivePolicy(
                    flow_snapshot_id=FLOW_SNAPSHOT_V1_ID,
                    policy_hash=_hash_dict(runtime_policy),
                    definition=runtime_policy,
                )
            )
        else:
            policy.policy_hash = _hash_dict(runtime_policy)
            policy.definition = runtime_policy
            session.add(policy)
        await session.execute(
            SnapshotBinding.__table__.delete().where(
                SnapshotBinding.flow_snapshot_id == FLOW_SNAPSHOT_V1_ID
            )
        )
        deployment_result = await session.execute(
            select(FlowDeployment).where(
                FlowDeployment.flow_deployment_id == FLOW_DEPLOYMENT_DEFAULT_ID
            )
        )
        deployment = deployment_result.scalar_one_or_none()
        if deployment is None:
            deployment = FlowDeployment(
                flow_deployment_id=FLOW_DEPLOYMENT_DEFAULT_ID,
                flow_id=FLOW_DEMO_ID,
                flow_version_id=FLOW_VERSION_V1_ID,
                flow_snapshot_id=FLOW_SNAPSHOT_V1_ID,
                environment="default",
                status="ACTIVE",
                deployed_by="system",
            )
            session.add(deployment)
        else:
            deployment.flow_id = FLOW_DEMO_ID
            deployment.flow_version_id = FLOW_VERSION_V1_ID
            deployment.flow_snapshot_id = FLOW_SNAPSHOT_V1_ID
            deployment.environment = "default"
            deployment.status = "ACTIVE"
            deployment.deployed_by = "system"
            session.add(deployment)

        tenant_result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == TENANT_DEMO_ID)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is not None and tenant.default_flow_version_id != FLOW_VERSION_V1_ID:
            tenant.default_flow_version_id = FLOW_VERSION_V1_ID
            session.add(tenant)

        await session.commit()
