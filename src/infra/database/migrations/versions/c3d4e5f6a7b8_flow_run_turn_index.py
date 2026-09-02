"""flow run turn index

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "flow_run",
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_flow_run_status_updated_at",
        "flow_run",
        ["status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_flow_run_status_updated_at", table_name="flow_run")
    op.drop_column("flow_run", "turn_index")
