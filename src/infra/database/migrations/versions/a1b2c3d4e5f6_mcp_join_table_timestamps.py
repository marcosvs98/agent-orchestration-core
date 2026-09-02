from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

_BOTH_TIMESTAMPS = (
    "mcp_server_tool",
    "mcp_server_vector_store",
    "mcp_server_user_prompt",
)


def upgrade() -> None:
    for table in _BOTH_TIMESTAMPS:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    op.add_column(
        "mcp_server_credential",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("mcp_server_credential", "updated_at")
    for table in _BOTH_TIMESTAMPS:
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
