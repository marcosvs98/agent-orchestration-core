"""Backbone schema for authoring/runtime separation."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260112_01_backbone"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = sa.dialects.postgresql.JSONB

    op.create_table(
        "tenant",
        sa.Column("tenant_id", uuid, primary_key=True, nullable=False),
        sa.Column("external_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ai_task",
        sa.Column("ai_task_id", uuid, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "model",
        sa.Column("model_id", uuid, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ai_execution_policy",
        sa.Column("ai_execution_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "tool",
        sa.Column("tool_id", uuid, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "vector_store",
        sa.Column("vector_store_id", uuid, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "session",
        sa.Column("session_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "flow",
        sa.Column("flow_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "flow_version",
        sa.Column("flow_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_id", uuid, sa.ForeignKey("flow.flow_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "node",
        sa.Column("node_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, sa.ForeignKey("flow_version.flow_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_task_id", uuid, sa.ForeignKey("ai_task.ai_task_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "router",
        sa.Column("router_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, sa.ForeignKey("flow_version.flow_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent",
        sa.Column("agent_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "condition_expression",
        sa.Column("condition_expression_id", uuid, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_version",
        sa.Column("agent_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_id", uuid, sa.ForeignKey("agent.agent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ai_execution_policy_version",
        sa.Column("ai_execution_policy_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("ai_execution_policy_id", uuid, sa.ForeignKey("ai_execution_policy.ai_execution_policy_id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", uuid, sa.ForeignKey("model.model_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "tool_config",
        sa.Column("tool_config_id", uuid, primary_key=True, nullable=False),
        sa.Column("tool_id", uuid, sa.ForeignKey("tool.tool_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "routing_rule",
        sa.Column("routing_rule_id", uuid, primary_key=True, nullable=False),
        sa.Column("router_id", uuid, sa.ForeignKey("router.router_id", ondelete="CASCADE"), nullable=False),
        sa.Column("condition_expression_id", uuid, sa.ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_node_id", uuid, sa.ForeignKey("node.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "node_agent_binding",
        sa.Column("node_agent_binding_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_id", uuid, sa.ForeignKey("node.node_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_version_id", uuid, sa.ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "node_ai_execution_policy_binding",
        sa.Column("node_ai_execution_policy_binding_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_id", uuid, sa.ForeignKey("node.node_id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_execution_policy_version_id", uuid, sa.ForeignKey("ai_execution_policy_version.ai_execution_policy_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_version_tool_binding",
        sa.Column("agent_version_tool_binding_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_version_id", uuid, sa.ForeignKey("agent_version.agent_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_config_id", uuid, sa.ForeignKey("tool_config.tool_config_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "rag_config",
        sa.Column("rag_config_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("vector_store_id", uuid, sa.ForeignKey("vector_store.vector_store_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "flow_run",
        sa.Column("flow_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, sa.ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", uuid, sa.ForeignKey("session.session_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "interaction",
        sa.Column("interaction_id", uuid, primary_key=True, nullable=False),
        sa.Column("session_id", uuid, sa.ForeignKey("session.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "node_run",
        sa.Column("node_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", uuid, sa.ForeignKey("node.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_run",
        sa.Column("agent_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_version_id", uuid, sa.ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "graph_state",
        sa.Column("graph_state_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="SET NULL")),
        sa.Column("state", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "escalation_policy",
        sa.Column("escalation_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "escalation",
        sa.Column("escalation_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("escalation_policy_id", uuid, sa.ForeignKey("escalation_policy.escalation_policy_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "onboarding",
        sa.Column("onboarding_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "onboarding_version",
        sa.Column("onboarding_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("onboarding_id", uuid, sa.ForeignKey("onboarding.onboarding_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "onboarding_run",
        sa.Column("onboarding_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("onboarding_version_id", uuid, sa.ForeignKey("onboarding_version.onboarding_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "onboarding_step",
        sa.Column("onboarding_step_id", uuid, primary_key=True, nullable=False),
        sa.Column("onboarding_version_id", uuid, sa.ForeignKey("onboarding_version.onboarding_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "step_run",
        sa.Column("step_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("onboarding_step_id", uuid, sa.ForeignKey("onboarding_step.onboarding_step_id", ondelete="CASCADE"), nullable=False),
        sa.Column("onboarding_run_id", uuid, sa.ForeignKey("onboarding_run.onboarding_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("step_run")
    op.drop_table("onboarding_step")
    op.drop_table("onboarding_run")
    op.drop_table("onboarding_version")
    op.drop_table("onboarding")
    op.drop_table("escalation")
    op.drop_table("escalation_policy")
    op.drop_table("graph_state")
    op.drop_table("agent_run")
    op.drop_table("node_run")
    op.drop_table("interaction")
    op.drop_table("flow_run")
    op.drop_table("rag_config")
    op.drop_table("agent_version_tool_binding")
    op.drop_table("tool_config")
    op.drop_table("tool")
    op.drop_table("node_ai_execution_policy_binding")
    op.drop_table("ai_execution_policy_version")
    op.drop_table("ai_execution_policy")
    op.drop_table("routing_rule")
    op.drop_table("condition_expression")
    op.drop_table("agent_version")
    op.drop_table("agent")
    op.drop_table("router")
    op.drop_table("node")
    op.drop_table("flow_version")
    op.drop_table("flow")
    op.drop_table("session")
    op.drop_table("vector_store")
    op.drop_table("model")
    op.drop_table("ai_task")
    op.drop_table("tenant")
