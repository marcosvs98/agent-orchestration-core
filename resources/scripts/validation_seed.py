from __future__ import annotations

import asyncio
import sys
from uuid import UUID
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from adapters.observability.logging import get_logger
from infra.database import get_db
from infra.database.models.governance.tenant import Tenant
from infra.database.models.conversation.session import Session
from infra.database.models.flow.flow import Flow
from infra.database.models.flow.flow_version import FlowVersion
from infra.database.models.flow.node import Node
from infra.database.models.flow.active_flow_version import ActiveFlowVersion
from infra.database.models.flow.flow_graph import FlowGraph
from infra.database.models.flow.flow_graph_draft import FlowGraphDraft
from infra.database.models.flow.flow_graph_snapshot import FlowGraphSnapshot
from infra.database.models.agent.agent import Agent
from infra.database.models.agent.agent_version import AgentVersion
from infra.database.models.agent.active_agent_version import ActiveAgentVersion
from infra.database.models.ai_policy.model import Model
from infra.database.models.ai_policy.execution_policy import AIExecutionPolicy
from infra.database.models.ai_policy.execution_policy_version import AIExecutionPolicyVersion
from domain.flows.schemas.graph import FlowGraphDefinition
from domain.flows.services.flow_graph_compiler import FlowGraphCompiler
from infra.database.models.governance.billing_policy import BillingPolicy
from infra.database.models.governance.billing_policy_version import BillingPolicyVersion
from infra.database.models.governance.active_billing_policy_version import ActiveBillingPolicyVersion
from infra.database.models.governance.execution_limit_policy import ExecutionLimitPolicy
from infra.database.models.governance.execution_limit_policy_version import ExecutionLimitPolicyVersion
from infra.database.models.governance.rate_limit_policy import RateLimitPolicy
from infra.database.models.governance.rate_limit_policy_version import RateLimitPolicyVersion
from infra.database.models.governance.access_policy import AccessPolicy
from infra.database.models.governance.access_policy_version import AccessPolicyVersion

logger = get_logger()

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("00000000-0000-0000-0000-00000000000a")
FLOW_ID = UUID("00000000-0000-0000-0000-000000000010")
FLOW_VERSION_ID = UUID("00000000-0000-0000-0000-000000000011")
NODE_ID = UUID("00000000-0000-0000-0000-000000000012")
AGENT_ID = UUID("00000000-0000-0000-0000-000000000020")
AGENT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000021")
MODEL_ID = UUID("00000000-0000-0000-0000-000000000030")
POLICY_ID = UUID("00000000-0000-0000-0000-000000000040")
POLICY_VERSION_ID = UUID("00000000-0000-0000-0000-000000000041")
EXEC_LIMIT_ID = UUID("00000000-0000-0000-0000-000000000050")
EXEC_LIMIT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000051")
RATE_LIMIT_ID = UUID("00000000-0000-0000-0000-000000000060")
RATE_LIMIT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000061")
DRAFT_FLOW_ID = UUID("00000000-0000-0000-0000-000000000070")
DRAFT_FLOW_VERSION_ID = UUID("00000000-0000-0000-0000-000000000071")
DRAFT_AGENT_ID = UUID("00000000-0000-0000-0000-000000000080")
DRAFT_AGENT_VERSION_ID = UUID("00000000-0000-0000-0000-000000000081")
ACCESS_POLICY_ID = UUID("00000000-0000-0000-0000-000000000090")
ACCESS_POLICY_VERSION_ID = UUID("00000000-0000-0000-0000-000000000091")
BILLING_POLICY_ID = UUID("00000000-0000-0000-0000-000000000100")
BILLING_POLICY_VERSION_ID = UUID("00000000-0000-0000-0000-000000000101")
GRAPH_NODE_INTENT_ID = UUID("00000000-0000-0000-0000-000000000201")
GRAPH_NODE_EXECUTE_ID = UUID("00000000-0000-0000-0000-000000000202")
GRAPH_NODE_CLARIFY_ID = UUID("00000000-0000-0000-0000-000000000203")
GRAPH_NODE_RESPOND_ID = UUID("00000000-0000-0000-0000-000000000204")
GRAPH_NODE_FALLBACK_ID = UUID("00000000-0000-0000-0000-000000000205")
FLOW_GRAPH_DRAFT_ID = UUID("00000000-0000-0000-0000-000000000310")
FLOW_GRAPH_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000320")


async def _add_if_not_exists(session, model_class, primary_key_attr, primary_key_value, **kwargs):
    result = await session.execute(
        select(model_class).where(getattr(model_class, primary_key_attr) == primary_key_value)
    )
    if result.scalar_one_or_none() is None:
        session.add(model_class(**{primary_key_attr: primary_key_value, **kwargs}))


async def upsert_validation_fixtures():
    async with get_db() as session:
        try:
            compiler = FlowGraphCompiler()
            await _add_if_not_exists(session, Tenant, "tenant_id", TENANT_ID)
            await _add_if_not_exists(session, Session, "session_id", SESSION_ID, tenant_id=TENANT_ID)

            await _add_if_not_exists(session, Model, "model_id", MODEL_ID, name="gpt-4o")
            await _add_if_not_exists(session, AIExecutionPolicy, "ai_execution_policy_id", POLICY_ID)
            await _add_if_not_exists(
                session,
                AIExecutionPolicyVersion,
                "ai_execution_policy_version_id",
                POLICY_VERSION_ID,
                ai_execution_policy_id=POLICY_ID,
                model_id=MODEL_ID,
                status="PUBLISHED",
            )

            await _add_if_not_exists(session, Flow, "flow_id", FLOW_ID, tenant_id=TENANT_ID)
            await _add_if_not_exists(
                session,
                FlowVersion,
                "flow_version_id",
                FLOW_VERSION_ID,
                flow_id=FLOW_ID,
                status="PUBLISHED",
                version_major=1,
                version_minor=0,
                version_patch=0,
            )
            await _add_if_not_exists(
                session, Node, "node_id", NODE_ID, flow_version_id=FLOW_VERSION_ID, ai_task_id=None
            )
            await _add_if_not_exists(
                session,
                Node,
                "node_id",
                GRAPH_NODE_INTENT_ID,
                flow_version_id=FLOW_VERSION_ID,
                ai_task_id=None,
            )
            await _add_if_not_exists(
                session,
                Node,
                "node_id",
                GRAPH_NODE_EXECUTE_ID,
                flow_version_id=FLOW_VERSION_ID,
                ai_task_id=None,
            )
            await _add_if_not_exists(
                session,
                Node,
                "node_id",
                GRAPH_NODE_CLARIFY_ID,
                flow_version_id=FLOW_VERSION_ID,
                ai_task_id=None,
            )
            await _add_if_not_exists(
                session,
                Node,
                "node_id",
                GRAPH_NODE_RESPOND_ID,
                flow_version_id=FLOW_VERSION_ID,
                ai_task_id=None,
            )
            await _add_if_not_exists(
                session,
                Node,
                "node_id",
                GRAPH_NODE_FALLBACK_ID,
                flow_version_id=FLOW_VERSION_ID,
                ai_task_id=None,
            )
            await _add_if_not_exists(session, Agent, "agent_id", AGENT_ID, tenant_id=TENANT_ID)
            await _add_if_not_exists(
                session,
                AgentVersion,
                "agent_version_id",
                AGENT_VERSION_ID,
                agent_id=AGENT_ID,
                ai_execution_policy_version_id=POLICY_VERSION_ID,
                status="PUBLISHED",
                version_major=1,
                version_minor=0,
                version_patch=0,
            )
            await _add_if_not_exists(
                session,
                ActiveAgentVersion,
                "agent_id",
                AGENT_ID,
                agent_version_id=AGENT_VERSION_ID,
                activated_by_principal_id="validation",
                justification="seed validation agent",
            )

            await _add_if_not_exists(
                session,
                ExecutionLimitPolicy,
                "execution_limit_policy_id",
                EXEC_LIMIT_ID,
                tenant_id=TENANT_ID,
                name="validation",
            )
            await _add_if_not_exists(
                session,
                ExecutionLimitPolicyVersion,
                "execution_limit_policy_version_id",
                EXEC_LIMIT_VERSION_ID,
                execution_limit_policy_id=EXEC_LIMIT_ID,
                status="PUBLISHED",
                max_total_runtime_seconds=120,
            )

            await _add_if_not_exists(
                session, RateLimitPolicy, "rate_limit_policy_id", RATE_LIMIT_ID, tenant_id=TENANT_ID, name="validation"
            )
            await _add_if_not_exists(
                session,
                RateLimitPolicyVersion,
                "rate_limit_policy_version_id",
                RATE_LIMIT_VERSION_ID,
                rate_limit_policy_id=RATE_LIMIT_ID,
                status="PUBLISHED",
                action="flow_run",
                principal_type="tenant",
                limit=100,
                window_seconds=60,
            )

            await _add_if_not_exists(
                session, AccessPolicy, "access_policy_id", ACCESS_POLICY_ID, tenant_id=TENANT_ID, name="validation"
            )
            await _add_if_not_exists(
                session,
                AccessPolicyVersion,
                "access_policy_version_id",
                ACCESS_POLICY_VERSION_ID,
                access_policy_id=ACCESS_POLICY_ID,
                status="PUBLISHED",
                version_major=1,
                version_minor=0,
                version_patch=0,
                config_hash=None,
                rules={"allow": ["flow:execute"], "deny": []},
            )

            await _add_if_not_exists(
                session, BillingPolicy, "billing_policy_id", BILLING_POLICY_ID, tenant_id=TENANT_ID, name="default"
            )
            await _add_if_not_exists(
                session,
                BillingPolicyVersion,
                "billing_policy_version_id",
                BILLING_POLICY_VERSION_ID,
                billing_policy_id=BILLING_POLICY_ID,
                status="PUBLISHED",
                version_major=1,
                version_minor=0,
                version_patch=0,
                config_hash=None,
                rules={
                    "max_cost_per_flow_run": 100.0,
                    "max_cost_per_agent_run": 50.0,
                    "max_tokens_per_agent_run": 500000,
                    "sla_seconds_per_flow_run": 120,
                },
            )
            await _add_if_not_exists(
                session,
                ActiveBillingPolicyVersion,
                "tenant_id",
                TENANT_ID,
                billing_policy_version_id=BILLING_POLICY_VERSION_ID,
                activated_by_principal_id="validation",
                justification="seed billing policy",
            )

            graph_definition = {
                "start_node": str(GRAPH_NODE_INTENT_ID),
                "nodes": {
                    str(GRAPH_NODE_INTENT_ID): {"type": "IntentToolSelectionNode", "config": {"output": {"confidence": 0.9, "validation_status": "VALID"}}},
                    str(GRAPH_NODE_EXECUTE_ID): {"type": "ToolExecutionNode", "config": {"output": {"execution_status": "SUCCESS"}}},
                    str(GRAPH_NODE_CLARIFY_ID): {"type": "ClarificationNode", "config": {"output": {"missing_fields": ["field"], "user_message": "clarify"}}},
                    str(GRAPH_NODE_RESPOND_ID): {"type": "ResponseNode", "config": {"output": {"message": "ok", "payload": {"done": True}}}},
                    str(GRAPH_NODE_FALLBACK_ID): {"type": "FallbackNode", "config": {"output": {"reason": "low_conf", "message": "fallback"}}},
                },
                "edges": [
                    {"from_node": str(GRAPH_NODE_INTENT_ID), "to_node": str(GRAPH_NODE_EXECUTE_ID), "condition": "validation_status == 'VALID' && confidence >= 0.85"},
                    {"from_node": str(GRAPH_NODE_INTENT_ID), "to_node": str(GRAPH_NODE_CLARIFY_ID), "condition": "validation_status == 'MISSING_FIELDS'"},
                    {"from_node": str(GRAPH_NODE_INTENT_ID), "to_node": str(GRAPH_NODE_FALLBACK_ID), "condition": "confidence < 0.85"},
                    {"from_node": str(GRAPH_NODE_EXECUTE_ID), "to_node": str(GRAPH_NODE_RESPOND_ID), "condition": "execution_status == 'SUCCESS'"},
                    {"from_node": str(GRAPH_NODE_EXECUTE_ID), "to_node": str(GRAPH_NODE_FALLBACK_ID), "condition": "execution_status == 'ERROR'"},
                ],
            }

            await _add_if_not_exists(
                session,
                FlowGraph,
                "flow_graph_id",
                UUID("00000000-0000-0000-0000-000000000300"),
                flow_version_id=FLOW_VERSION_ID,
                definition=graph_definition,
                created_by="validation",
            )

            definition_model = FlowGraphDefinition.model_validate(graph_definition)
            snapshot_payload, graph_hash = compiler.compile(definition_model)
            await _add_if_not_exists(
                session,
                FlowGraphDraft,
                "flow_graph_draft_id",
                FLOW_GRAPH_DRAFT_ID,
                flow_version_id=FLOW_VERSION_ID,
                definition=graph_definition,
                status="VALIDATED",
                created_by="validation",
                validated_by="validation",
            )
            await _add_if_not_exists(
                session,
                FlowGraphSnapshot,
                "flow_graph_snapshot_id",
                FLOW_GRAPH_SNAPSHOT_ID,
                flow_version_id=FLOW_VERSION_ID,
                snapshot=snapshot_payload,
                graph_hash=graph_hash,
                compiled_by="validation",
            )
            await _add_if_not_exists(
                session,
                ActiveFlowVersion,
                "flow_id",
                FLOW_ID,
                flow_version_id=FLOW_VERSION_ID,
                activated_by_principal_id="validation",
                justification="seed validation flow",
                flow_graph_snapshot_id=FLOW_GRAPH_SNAPSHOT_ID,
            )

            await _add_if_not_exists(session, Flow, "flow_id", DRAFT_FLOW_ID, tenant_id=TENANT_ID)
            await _add_if_not_exists(
                session,
                FlowVersion,
                "flow_version_id",
                DRAFT_FLOW_VERSION_ID,
                flow_id=DRAFT_FLOW_ID,
                status="DRAFT",
                version_major=1,
                version_minor=0,
                version_patch=0,
            )

            await _add_if_not_exists(session, Agent, "agent_id", DRAFT_AGENT_ID, tenant_id=TENANT_ID)
            await _add_if_not_exists(
                session,
                AgentVersion,
                "agent_version_id",
                DRAFT_AGENT_VERSION_ID,
                agent_id=DRAFT_AGENT_ID,
                ai_execution_policy_version_id=POLICY_VERSION_ID,
                status="DRAFT",
                version_major=0,
                version_minor=1,
                version_patch=0,
            )

            await session.commit()
            logger.info("Validation fixtures seeded")
        except IntegrityError:
            await session.rollback()
            logger.info("Validation fixtures already exist, skipping")


async def main():
    await upsert_validation_fixtures()


if __name__ == "__main__":
    asyncio.run(main())
