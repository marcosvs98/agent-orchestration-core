"""Access policy versioning (Planning 14)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_04_access_policy"
down_revision: Union[str, None] = "20260113_03_execution_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "access_policy",
        sa.Column("access_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_access_policy_tenant_id", "access_policy", ["tenant_id"])
    op.create_index("ix_access_policy_name", "access_policy", ["name"])

    op.create_table(
        "access_policy_version",
        sa.Column("access_policy_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("access_policy_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["access_policy_id"], ["access_policy.access_policy_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "access_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_access_policy_version_semver",
        ),
    )
    op.create_index("ix_access_policy_version_status", "access_policy_version", ["status"])


def downgrade() -> None:
    op.drop_index("ix_access_policy_version_status", table_name="access_policy_version")
    op.drop_table("access_policy_version")

    op.drop_index("ix_access_policy_name", table_name="access_policy")
    op.drop_index("ix_access_policy_tenant_id", table_name="access_policy")
    op.drop_table("access_policy")
