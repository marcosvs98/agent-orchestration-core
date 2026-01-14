"""Planning 21 - runtime_policy table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260121_01_runtime_policy"
down_revision: Union[str, None] = "20260119_01_flow_graph_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "runtime_policy",
        sa.Column("runtime_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("flow_id", uuid, sa.ForeignKey("flow.flow_id", ondelete="CASCADE"), nullable=True),
        sa.Column("version", sa.String(length=16), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("policy_definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index(
        "ix_runtime_policy_active_scope",
        "runtime_policy",
        ["tenant_id", "scope", "flow_id"],
        unique=False,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_policy_active_scope", table_name="runtime_policy")
    op.drop_table("runtime_policy")
