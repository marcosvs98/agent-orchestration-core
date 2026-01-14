"""Planning 17 - flow_graph table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260117_01_flow_graph"
down_revision: Union[str, None] = "20260116_01_billing_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "flow_graph",
        sa.Column("flow_graph_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, nullable=False, unique=True),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.flow_version_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_flow_graph_flow_version_id", "flow_graph", ["flow_version_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_flow_graph_flow_version_id", table_name="flow_graph")
    op.drop_table("flow_graph")
