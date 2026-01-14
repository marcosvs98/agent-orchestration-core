"""Authoring event log for publish/activate governance (Planning 15)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_08_authoring_event"
down_revision: Union[str, None] = "20260113_07_activation_pointers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "authoring_event",
        sa.Column("authoring_event_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", uuid, nullable=False),
        sa.Column("version_id", uuid, nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_authoring_event_tenant_id", "authoring_event", ["tenant_id"])
    op.create_index("ix_authoring_event_resource", "authoring_event", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_index("ix_authoring_event_resource", table_name="authoring_event")
    op.drop_index("ix_authoring_event_tenant_id", table_name="authoring_event")
    op.drop_table("authoring_event")
