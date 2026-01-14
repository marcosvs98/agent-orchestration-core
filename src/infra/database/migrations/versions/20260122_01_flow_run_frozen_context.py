"""Planning 22 - flow_run frozen context fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260122_01_flow_run_frozen_context"
down_revision: Union[str, None] = "20260121_01_runtime_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column(
        "flow_run",
        sa.Column(
            "flow_graph_snapshot_id",
            uuid,
            sa.ForeignKey("flow_graph_snapshot.flow_graph_snapshot_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("flow_run", sa.Column("execution_plan_hash", sa.String(length=128), nullable=True))
    op.add_column("flow_run", sa.Column("runtime_policy_hash", sa.String(length=128), nullable=True))
    op.add_column("flow_run", sa.Column("tool_catalog_hash", sa.String(length=128), nullable=True))
    op.add_column("flow_run", sa.Column("llm_provider_config_hash", sa.String(length=128), nullable=True))
    op.add_column("flow_run", sa.Column("trace_id", uuid, nullable=True))

    op.create_index("ix_flow_run_trace_id", "flow_run", ["trace_id"], unique=False)
    op.create_index("ix_flow_run_flow_graph_snapshot_id", "flow_run", ["flow_graph_snapshot_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_flow_run_flow_graph_snapshot_id", table_name="flow_run")
    op.drop_index("ix_flow_run_trace_id", table_name="flow_run")

    op.drop_column("flow_run", "trace_id")
    op.drop_column("flow_run", "llm_provider_config_hash")
    op.drop_column("flow_run", "tool_catalog_hash")
    op.drop_column("flow_run", "runtime_policy_hash")
    op.drop_column("flow_run", "execution_plan_hash")
    op.drop_column("flow_run", "flow_graph_snapshot_id")
