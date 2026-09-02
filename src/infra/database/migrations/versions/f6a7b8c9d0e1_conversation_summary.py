"""conversation summary carry-forward

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-15 00:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_summary",
        sa.Column("conversation_summary_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("conversation_key", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("turns_covered", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "estimated_tokens_covered", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("provider_conversation_id", sa.String(length=128), nullable=True),
        sa.Column("rollover_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_rolled_over_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_conversation_summary_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_summary_id", name=op.f("pk_conversation_summary")
        ),
        sa.UniqueConstraint(
            "conversation_key", name="uq_conversation_summary_conversation_key"
        ),
    )
    op.create_index(
        "ix_conversation_summary_tenant_id",
        "conversation_summary",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_summary_tenant_id", table_name="conversation_summary")
    op.drop_table("conversation_summary")
