"""tenant mcp credential

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_mcp_credential",
        sa.Column("tenant_mcp_credential_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("mcp_access_key", sa.Text(), nullable=False),
        sa.Column("outbound_api_key", sa.Text(), nullable=False),
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
            name=op.f("fk_tenant_mcp_credential_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.mcp_server_id"],
            name=op.f("fk_tenant_mcp_credential_mcp_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_mcp_credential_id",
            name=op.f("pk_tenant_mcp_credential"),
        ),
    )
    op.create_index(
        "ix_tenant_mcp_credential_tenant_active",
        "tenant_mcp_credential",
        ["tenant_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tenant_mcp_credential (
                tenant_mcp_credential_id,
                tenant_id,
                mcp_server_id,
                mcp_access_key,
                outbound_api_key,
                revoked_at
            )
            SELECT
                '00000000-0000-0000-0000-000000001600'::uuid,
                '00000000-0000-0000-0000-000000000100'::uuid,
                '00000000-0000-0000-0000-000000001500'::uuid,
                'ccdc7f91-7760-431d-8a72-2d6d4b7c7b61',
                'demo-outbound-api-key-v1',
                NULL
            WHERE EXISTS (
                SELECT 1 FROM tenant
                WHERE tenant_id = '00000000-0000-0000-0000-000000000100'::uuid
            )
            AND EXISTS (
                SELECT 1 FROM mcp_server
                WHERE mcp_server_id = '00000000-0000-0000-0000-000000001500'::uuid
            )
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_mcp_credential_tenant_active",
        table_name="tenant_mcp_credential",
    )
    op.drop_table("tenant_mcp_credential")
