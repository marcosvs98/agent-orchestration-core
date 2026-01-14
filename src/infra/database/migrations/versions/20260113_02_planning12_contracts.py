"""Planning (12) adjusted: Interaction contract, FlowRun link, ToolConfig config, ResponseArtifact."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_02_planning12_contracts"
down_revision: Union[str, None] = "20260113_01_ai_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    # Interaction: enrich contract fields
    op.add_column(
        "interaction",
        sa.Column("channel", sa.String(length=64), nullable=False, server_default="http"),
    )
    op.add_column(
        "interaction",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "interaction",
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "interaction",
        sa.Column(
            "interaction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "interaction",
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "interaction",
        sa.Column("request_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "interaction",
        sa.Column("trace_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "interaction",
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # FlowRun: link to Interaction
    op.add_column(
        "flow_run",
        sa.Column(
            "interaction_id",
            uuid,
            sa.ForeignKey("interaction.interaction_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_flow_run_interaction_id", "flow_run", ["interaction_id"])

    # Tool: add name
    op.add_column("tool", sa.Column("name", sa.String(length=255), nullable=True))
    op.create_index("ix_tool_name", "tool", ["name"], unique=True)

    # ToolConfig: add config JSON
    op.add_column(
        "tool_config",
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # ResponseArtifact
    op.create_table(
        "response_artifact",
        sa.Column("response_artifact_id", uuid, primary_key=True, nullable=False),
        sa.Column(
            "interaction_id",
            uuid,
            sa.ForeignKey("interaction.interaction_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "flow_run_id",
            uuid,
            sa.ForeignKey("flow_run.flow_run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_response_artifact_flow_run_id", "response_artifact", ["flow_run_id"])
    op.create_index("ix_response_artifact_interaction_id", "response_artifact", ["interaction_id"])


def downgrade() -> None:
    op.drop_index("ix_response_artifact_interaction_id", table_name="response_artifact")
    op.drop_index("ix_response_artifact_flow_run_id", table_name="response_artifact")
    op.drop_table("response_artifact")

    op.drop_column("tool_config", "config")

    op.drop_index("ix_tool_name", table_name="tool")
    op.drop_column("tool", "name")

    op.drop_index("ix_flow_run_interaction_id", table_name="flow_run")
    op.drop_column("flow_run", "interaction_id")

    op.drop_column("interaction", "received_at")
    op.drop_column("interaction", "trace_id")
    op.drop_column("interaction", "request_id")
    op.drop_column("interaction", "external_message_id")
    op.drop_column("interaction", "interaction_metadata")
    op.drop_column("interaction", "headers")
    op.drop_column("interaction", "payload")
    op.drop_column("interaction", "channel")
