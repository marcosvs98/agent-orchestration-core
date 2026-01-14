"""Planning 19 - flow graph draft and snapshot."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260119_01_flow_graph_snapshot"
down_revision: Union[str, None] = "20260117_01_flow_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "flow_graph_draft",
        sa.Column("flow_graph_draft_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, nullable=False, unique=True),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_by", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.flow_version_id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "flow_graph_snapshot",
        sa.Column("flow_graph_snapshot_id", uuid, primary_key=True, nullable=False),
        sa.Column("flow_version_id", uuid, nullable=False, unique=True),
        sa.Column("graph_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("compiled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("compiled_by", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.flow_version_id"], ondelete="RESTRICT"),
    )

    op.add_column(
        "active_flow_version",
        sa.Column("flow_graph_snapshot_id", uuid, nullable=True),
    )
    op.create_foreign_key(
        "fk_active_flow_version_graph_snapshot",
        "active_flow_version",
        "flow_graph_snapshot",
        ["flow_graph_snapshot_id"],
        ["flow_graph_snapshot_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_active_flow_version_graph_snapshot", "active_flow_version", type_="foreignkey")
    op.drop_column("active_flow_version", "flow_graph_snapshot_id")
    op.drop_table("flow_graph_snapshot")
    op.drop_table("flow_graph_draft")
