"""agent run ai execution policy version

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15 00:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_run",
        sa.Column("ai_execution_policy_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_agent_run_ai_execution_policy_version_id_ai_execution_policy_version"),
        "agent_run",
        "ai_execution_policy_version",
        ["ai_execution_policy_version_id"],
        ["ai_execution_policy_version_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_agent_run_ai_execution_policy_version_id_ai_execution_policy_version"),
        "agent_run",
        type_="foreignkey",
    )
    op.drop_column("agent_run", "ai_execution_policy_version_id")
