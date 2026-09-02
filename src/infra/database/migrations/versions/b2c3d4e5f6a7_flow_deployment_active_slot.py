from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_flow_deployment_slot", "flow_deployment", type_="unique")
    op.create_index(
        "uq_flow_deployment_active_slot",
        "flow_deployment",
        ["flow_id", "environment"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_flow_deployment_active_slot", table_name="flow_deployment")
    op.create_unique_constraint(
        "uq_flow_deployment_slot",
        "flow_deployment",
        ["flow_id", "environment", "status"],
    )
