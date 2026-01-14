"""Execution runs state machine fields, ToolRun, and DLQ logical entity."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260112_02_execution_runs"
down_revision: Union[str, None] = "20260112_01_backbone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = sa.dialects.postgresql.JSONB

    # FlowRun
    op.add_column("flow_run", sa.Column("origin_flow_run_id", uuid, nullable=True))
    op.create_foreign_key(
        "fk_flow_run_origin_flow_run_id_flow_run",
        "flow_run",
        "flow_run",
        ["origin_flow_run_id"],
        ["flow_run_id"],
        ondelete="SET NULL",
    )
    op.add_column("flow_run", sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False))
    op.add_column("flow_run", sa.Column("correlation_id", uuid, nullable=False))
    op.add_column("flow_run", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("flow_run", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("flow_run", sa.Column("input", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("flow_run", sa.Column("output", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("flow_run", sa.Column("error", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_index("ix_flow_run_status", "flow_run", ["status"])
    op.create_index("ix_flow_run_correlation_id", "flow_run", ["correlation_id"])

    # NodeRun
    op.add_column("node_run", sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False))
    op.add_column("node_run", sa.Column("correlation_id", uuid, nullable=False))
    op.add_column("node_run", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("node_run", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("node_run", sa.Column("input", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("node_run", sa.Column("output", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("node_run", sa.Column("error", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_index("ix_node_run_status", "node_run", ["status"])
    op.create_index("ix_node_run_correlation_id", "node_run", ["correlation_id"])

    # AgentRun
    op.add_column("agent_run", sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False))
    op.add_column("agent_run", sa.Column("correlation_id", uuid, nullable=False))
    op.add_column("agent_run", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_run", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_run", sa.Column("input", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("agent_run", sa.Column("output", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("agent_run", sa.Column("error", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_index("ix_agent_run_status", "agent_run", ["status"])
    op.create_index("ix_agent_run_correlation_id", "agent_run", ["correlation_id"])

    # ToolRun
    op.create_table(
        "tool_run",
        sa.Column("tool_run_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_run_id", uuid, sa.ForeignKey("agent_run.agent_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_config_id", uuid, sa.ForeignKey("tool_config.tool_config_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("has_side_effect", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tool_run_status", "tool_run", ["status"])
    op.create_index("ix_tool_run_correlation_id", "tool_run", ["correlation_id"])

    # DLQ logical entity: RunFailure
    op.create_table(
        "run_failure",
        sa.Column("run_failure_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_run_id", uuid, sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"), nullable=True),
        sa.Column("node_run_id", uuid, sa.ForeignKey("node_run.node_run_id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_run_id", uuid, sa.ForeignKey("agent_run.agent_run_id", ondelete="CASCADE"), nullable=True),
        sa.Column("tool_run_id", uuid, sa.ForeignKey("tool_run.tool_run_id", ondelete="CASCADE"), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=False),
        sa.Column("error", jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_run_failure_correlation_id", "run_failure", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_run_failure_correlation_id", table_name="run_failure")
    op.drop_table("run_failure")

    op.drop_index("ix_tool_run_correlation_id", table_name="tool_run")
    op.drop_index("ix_tool_run_status", table_name="tool_run")
    op.drop_table("tool_run")

    op.drop_index("ix_agent_run_correlation_id", table_name="agent_run")
    op.drop_index("ix_agent_run_status", table_name="agent_run")
    op.drop_column("agent_run", "error")
    op.drop_column("agent_run", "output")
    op.drop_column("agent_run", "input")
    op.drop_column("agent_run", "finished_at")
    op.drop_column("agent_run", "started_at")
    op.drop_column("agent_run", "correlation_id")
    op.drop_column("agent_run", "status")

    op.drop_index("ix_node_run_correlation_id", table_name="node_run")
    op.drop_index("ix_node_run_status", table_name="node_run")
    op.drop_column("node_run", "error")
    op.drop_column("node_run", "output")
    op.drop_column("node_run", "input")
    op.drop_column("node_run", "finished_at")
    op.drop_column("node_run", "started_at")
    op.drop_column("node_run", "correlation_id")
    op.drop_column("node_run", "status")

    op.drop_index("ix_flow_run_correlation_id", table_name="flow_run")
    op.drop_index("ix_flow_run_status", table_name="flow_run")
    op.drop_column("flow_run", "error")
    op.drop_column("flow_run", "output")
    op.drop_column("flow_run", "input")
    op.drop_column("flow_run", "finished_at")
    op.drop_column("flow_run", "started_at")
    op.drop_column("flow_run", "correlation_id")
    op.drop_column("flow_run", "status")
    op.drop_constraint(
        "fk_flow_run_origin_flow_run_id_flow_run",
        "flow_run",
        type_="foreignkey",
    )
    op.drop_column("flow_run", "origin_flow_run_id")
