"""flow run temporal dispatch

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-08-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "flow_run",
        sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "flow_run",
        sa.Column("temporal_run_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_flow_run_temporal_workflow_id",
        "flow_run",
        ["temporal_workflow_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_flow_run_temporal_workflow_id", table_name="flow_run")
    op.drop_column("flow_run", "temporal_run_id")
    op.drop_column("flow_run", "temporal_workflow_id")
