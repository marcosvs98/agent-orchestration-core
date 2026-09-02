"""llm usage ledger

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-15 00:20:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_ledger",
        sa.Column("llm_usage_ledger_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=True),
        sa.Column("node_run_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_model", sa.String(length=128), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=True),
        sa.Column("inference_layer", sa.String(length=32), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(18, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            name=op.f("fk_llm_usage_ledger_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_llm_usage_ledger_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_run.node_run_id"],
            name=op.f("fk_llm_usage_ledger_node_run_id_node_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name=op.f("fk_llm_usage_ledger_agent_run_id_agent_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("llm_usage_ledger_id", name=op.f("pk_llm_usage_ledger")),
    )
    op.create_index(
        "ix_llm_usage_ledger_tenant_id_occurred_at",
        "llm_usage_ledger",
        ["tenant_id", "occurred_at"],
    )
    op.create_index(
        "ix_llm_usage_ledger_flow_run_id",
        "llm_usage_ledger",
        ["flow_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_ledger_flow_run_id", table_name="llm_usage_ledger")
    op.drop_index("ix_llm_usage_ledger_tenant_id_occurred_at", table_name="llm_usage_ledger")
    op.drop_table("llm_usage_ledger")
