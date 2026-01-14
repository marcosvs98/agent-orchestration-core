"""Activation pointers for immutable versions (Planning 15)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_07_activation_pointers"
down_revision: Union[str, None] = "20260113_06_rate_limit_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "active_flow_version",
        sa.Column("flow_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["flow_id"], ["flow.flow_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.flow_version_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_active_flow_version_flow_version_id", "active_flow_version", ["flow_version_id"])

    op.create_table(
        "active_agent_version",
        sa.Column("agent_id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_version_id", uuid, nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.agent_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_version.agent_version_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_active_agent_version_agent_version_id", "active_agent_version", ["agent_version_id"])


def downgrade() -> None:
    op.drop_index("ix_active_agent_version_agent_version_id", table_name="active_agent_version")
    op.drop_table("active_agent_version")
    op.drop_index("ix_active_flow_version_flow_version_id", table_name="active_flow_version")
    op.drop_table("active_flow_version")
