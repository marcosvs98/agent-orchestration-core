"""Rate limit policy versioning (Planning 14)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_06_rate_limit_policy"
down_revision: Union[str, None] = "20260113_05_exec_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "rate_limit_policy",
        sa.Column("rate_limit_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_rate_limit_policy_tenant_id", "rate_limit_policy", ["tenant_id"])

    op.create_table(
        "rate_limit_policy_version",
        sa.Column("rate_limit_policy_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("rate_limit_policy_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rate_limit_policy_id"], ["rate_limit_policy.rate_limit_policy_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "rate_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rate_limit_policy_version_semver",
        ),
    )
    op.create_index("ix_rate_limit_policy_version_status", "rate_limit_policy_version", ["status"])
    op.create_index("ix_rate_limit_policy_version_action", "rate_limit_policy_version", ["action"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_policy_version_action", table_name="rate_limit_policy_version")
    op.drop_index("ix_rate_limit_policy_version_status", table_name="rate_limit_policy_version")
    op.drop_table("rate_limit_policy_version")
    op.drop_index("ix_rate_limit_policy_tenant_id", table_name="rate_limit_policy")
    op.drop_table("rate_limit_policy")
