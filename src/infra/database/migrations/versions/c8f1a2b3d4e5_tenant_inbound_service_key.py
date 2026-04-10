"""tenant inbound service key

Revision ID: c8f1a2b3d4e5
Revises: 861cb744f4f0
Create Date: 2026-04-06

"""

from alembic import op
import sqlalchemy as sa


revision = "c8f1a2b3d4e5"
down_revision = "861cb744f4f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_inbound_service_key",
        sa.Column("inbound_service_key_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_tenant_inbound_service_key_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "inbound_service_key_id",
            name=op.f("pk_tenant_inbound_service_key"),
        ),
    )
    op.create_index(
        "uq_tenant_inbound_service_key_hash",
        "tenant_inbound_service_key",
        ["key_hash"],
        unique=True,
    )
    # On first install the tenant row usually does not exist yet (created by demo seeds),
    # so this INSERT often inserts 0 rows. Demo seed seed_01_tenant also upserts this key.
    op.execute(
        sa.text(
            """
            INSERT INTO tenant_inbound_service_key (
                inbound_service_key_id,
                tenant_id,
                key_hash,
                revoked_at
            )
            SELECT
                '00000000-0000-0000-0000-000000000950'::uuid,
                '00000000-0000-0000-0000-000000000100'::uuid,
                'b6645a40a442a9ff4d3a62e4a3078e6f614abad09eab92a9604a3e0e62028646',
                NULL
            WHERE EXISTS (
                SELECT 1 FROM tenant
                WHERE tenant_id = '00000000-0000-0000-0000-000000000100'::uuid
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "uq_tenant_inbound_service_key_hash",
        table_name="tenant_inbound_service_key",
    )
    op.drop_table("tenant_inbound_service_key")
