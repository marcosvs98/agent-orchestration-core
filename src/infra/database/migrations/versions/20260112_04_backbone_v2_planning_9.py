"""Backbone v2 - Planning (9) canonical model (breaking)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260112_04_backbone_v2"
down_revision: Union[str, None] = "20260112_03_versioning_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = sa.dialects.postgresql.JSONB

    # Drop dependents to recreate with new FK layout (breaking).
    op.drop_table("run_failure")
    op.drop_table("tool_run")
    op.drop_table("agent_run")
    op.drop_table("routing_rule")
    op.drop_table("router")

    # Authoring adjustments
    op.add_column(
        "agent_version",
        sa.Column(
            "ai_execution_policy_version_id",
            uuid,
            sa.ForeignKey("ai_execution_policy_version.ai_execution_policy_version_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_version",
        sa.Column(
            "rag_config_id",
            uuid,
            sa.ForeignKey("rag_config.rag_config_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    op.create_table(
        "router",
        sa.Column("router_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_id", uuid, sa.ForeignKey("node.node_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "routing_rule",
        sa.Column("routing_rule_id", uuid, primary_key=True, nullable=False),
        sa.Column("router_id", uuid, sa.ForeignKey("router.router_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "condition_expression_id",
            uuid,
            sa.ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_node_id", uuid, sa.ForeignKey("node.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_node_id", uuid, sa.ForeignKey("node.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # EscalationPolicy link to condition_expression
    op.add_column(
        "escalation_policy",
        sa.Column(
            "condition_expression_id",
            uuid,
            sa.ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    # Runtime adjustments
    op.create_table(
        "agent_run",
        sa.Column("agent_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "agent_version_id",
            uuid,
            sa.ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ai_execution_policy_version_id",
            uuid,
            sa.ForeignKey("ai_execution_policy_version.ai_execution_policy_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tool_run",
        sa.Column("tool_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_run_id", uuid, sa.ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_config_id", uuid, sa.ForeignKey("tool_config.tool_config_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("has_side_effect", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Observability
    op.create_table(
        "execution_event",
        sa.Column("execution_event_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Drop new tables
    op.drop_table("execution_event")
    op.drop_table("tool_run")
    op.drop_table("agent_run")
    op.drop_table("routing_rule")
    op.drop_table("router")

    # Remove added columns
    op.drop_column("agent_version", "rag_config_id")
    op.drop_column("agent_version", "ai_execution_policy_version_id")
    op.drop_column("escalation_policy", "condition_expression_id")

    # Recreate legacy router/routing_rule/agent_run/tool_run (minimal fields)
    op.create_table(
        "router",
        sa.Column("router_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, sa.ForeignKey("flow_version.flow_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "routing_rule",
        sa.Column("routing_rule_id", uuid, primary_key=True, nullable=False),
        sa.Column("router_id", uuid, sa.ForeignKey("router.router_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "condition_expression_id",
            uuid,
            sa.ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("target_node_id", uuid, sa.ForeignKey("node.node_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "agent_run",
        sa.Column("agent_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "agent_version_id",
            uuid,
            sa.ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tool_run",
        sa.Column("tool_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_run_id", uuid, sa.ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_config_id", uuid, sa.ForeignKey("tool_config.tool_config_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("has_side_effect", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
