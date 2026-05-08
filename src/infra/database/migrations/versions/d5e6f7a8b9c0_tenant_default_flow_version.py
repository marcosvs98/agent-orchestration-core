"""tenant default flow version

Revision ID: d5e6f7a8b9c0
Revises: c8f1a2b3d4e5
Create Date: 2026-05-07

"""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c8f1a2b3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("default_flow_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tenant_default_flow_version_id",
        "tenant",
        "flow_version",
        ["default_flow_version_id"],
        ["flow_version_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenant_default_flow_version_id", "tenant", type_="foreignkey")
    op.drop_column("tenant", "default_flow_version_id")
