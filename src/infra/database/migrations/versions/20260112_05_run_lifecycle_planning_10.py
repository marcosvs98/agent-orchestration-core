"""Planning (10) run lifecycle: canonical_status, waiting fields, flow_run_lock."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260112_05_run_lifecycle"
down_revision: Union[str, None] = "20260112_04_backbone_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    # canonical_status on runs
    for table, default in [
        ("flow_run", "CREATED"),
        ("node_run", "PENDING"),
        ("agent_run", "CREATED"),
        ("tool_run", "CREATED"),
    ]:
        op.add_column(table, sa.Column("canonical_status", sa.String(length=32), server_default=default, nullable=False))

    # Waiting fields on flow_run
    op.add_column("flow_run", sa.Column("waiting_reason", sa.String(length=255), nullable=True))
    op.add_column("flow_run", sa.Column("waiting_deadline_at", sa.DateTime(timezone=True), nullable=True))

    # flow_run_lock table
    op.create_table(
        "flow_run_lock",
        sa.Column(
            "flow_run_id",
            uuid,
            sa.ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", uuid, nullable=True),
    )

    # ExecutionEvent: add correlation_id for observability
    op.add_column("execution_event", sa.Column("correlation_id", uuid, nullable=True))
    op.create_index("ix_execution_event_flow_run_id", "execution_event", ["flow_run_id"])
    op.create_index("ix_execution_event_correlation_id", "execution_event", ["correlation_id"])


def downgrade() -> None:
    # drop indexes and column
    op.drop_index("ix_execution_event_correlation_id", table_name="execution_event")
    op.drop_index("ix_execution_event_flow_run_id", table_name="execution_event")
    op.drop_column("execution_event", "correlation_id")

    # drop lock table
    op.drop_table("flow_run_lock")

    # remove waiting fields
    op.drop_column("flow_run", "waiting_deadline_at")
    op.drop_column("flow_run", "waiting_reason")

    # remove canonical_status
    for table in ["tool_run", "agent_run", "node_run", "flow_run"]:
        op.drop_column(table, "canonical_status")
