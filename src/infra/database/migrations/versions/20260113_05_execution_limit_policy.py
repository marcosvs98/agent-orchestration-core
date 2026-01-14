"""Execution limit policy versioning (Planning 14)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_05_exec_limit"
down_revision: Union[str, None] = "20260113_04_access_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        "execution_limit_policy",
        sa.Column("execution_limit_policy_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.tenant_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_execution_limit_policy_tenant_id", "execution_limit_policy", ["tenant_id"])

    op.create_table(
        "execution_limit_policy_version",
        sa.Column("execution_limit_policy_version_id", uuid, primary_key=True, nullable=False),
        sa.Column("execution_limit_policy_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("max_nodes_per_flow_run", sa.Integer(), server_default="100", nullable=False),
        sa.Column("max_node_runs_per_flow_run", sa.Integer(), server_default="500", nullable=False),
        sa.Column("max_agent_runs_per_interaction", sa.Integer(), server_default="100", nullable=False),
        sa.Column("max_tool_runs_per_flow_run", sa.Integer(), server_default="200", nullable=False),
        sa.Column("max_tokens_per_agent_run", sa.Integer(), server_default="8192", nullable=False),
        sa.Column("max_total_runtime_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_limit_policy_id"],
            ["execution_limit_policy.execution_limit_policy_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "execution_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_execution_limit_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_execution_limit_policy_version_status",
        "execution_limit_policy_version",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_limit_policy_version_status", table_name="execution_limit_policy_version")
    op.drop_table("execution_limit_policy_version")
    op.drop_index("ix_execution_limit_policy_tenant_id", table_name="execution_limit_policy")
    op.drop_table("execution_limit_policy")
