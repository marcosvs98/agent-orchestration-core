"""Planning 16 - billing policy tables and run stamping fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260116_01_billing_policy"
down_revision: Union[str, None] = "20260113_08_authoring_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "billing_policy",
        sa.Column("billing_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_billing_policy_tenant_id", "billing_policy", ["tenant_id"])

    op.create_table(
        "billing_policy_version",
        sa.Column("billing_policy_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("billing_policy_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_patch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["billing_policy_id"], ["billing_policy.billing_policy_id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_billing_policy_version_policy", "billing_policy_version", ["billing_policy_id"])
    op.create_index("ix_billing_policy_version_status", "billing_policy_version", ["status"])

    op.create_table(
        "active_billing_policy_version",
        sa.Column("tenant_id", uuid, primary_key=True, nullable=False),
        sa.Column("billing_policy_version_id", uuid, nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["billing_policy_version_id"],
            ["billing_policy_version.billing_policy_version_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_active_billing_policy_version_policy_version_id",
        "active_billing_policy_version",
        ["billing_policy_version_id"],
    )

    op.add_column(
        "agent_run",
        sa.Column("billing_policy_version_id", uuid, nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_run_billing_policy_version",
        "agent_run",
        "billing_policy_version",
        ["billing_policy_version_id"],
        ["billing_policy_version_id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "tool_run",
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "tool_run",
        sa.Column("billing_policy_version_id", uuid, nullable=True),
    )
    op.create_foreign_key(
        "fk_tool_run_billing_policy_version",
        "tool_run",
        "billing_policy_version",
        ["billing_policy_version_id"],
        ["billing_policy_version_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tool_run_billing_policy_version", "tool_run", type_="foreignkey")
    op.drop_column("tool_run", "billing_policy_version_id")
    op.drop_column("tool_run", "estimated_cost")

    op.drop_constraint("fk_agent_run_billing_policy_version", "agent_run", type_="foreignkey")
    op.drop_column("agent_run", "billing_policy_version_id")

    op.drop_index("ix_active_billing_policy_version_policy_version_id", table_name="active_billing_policy_version")
    op.drop_table("active_billing_policy_version")

    op.drop_index("ix_billing_policy_version_status", table_name="billing_policy_version")
    op.drop_index("ix_billing_policy_version_policy", table_name="billing_policy_version")
    op.drop_table("billing_policy_version")

    op.drop_index("ix_billing_policy_tenant_id", table_name="billing_policy")
    op.drop_table("billing_policy")
