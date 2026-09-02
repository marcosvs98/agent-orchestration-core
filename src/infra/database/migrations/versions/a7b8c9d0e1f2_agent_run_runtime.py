"""agent run runtime: standalone runs, transcript, events, artifacts, a2a delegation

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_run", sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=True))
    op.add_column("agent_run", sa.Column("agent_id", PG_UUID(as_uuid=True), nullable=True))
    op.add_column(
        "agent_run",
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="FLOW_NODE"),
    )
    op.add_column(
        "agent_run", sa.Column("parent_agent_run_id", PG_UUID(as_uuid=True), nullable=True)
    )
    op.add_column("agent_run", sa.Column("root_agent_run_id", PG_UUID(as_uuid=True), nullable=True))
    op.add_column(
        "agent_run",
        sa.Column("delegation_depth", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_run",
        sa.Column(
            "context_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.add_column(
        "agent_run",
        sa.Column("tool_grant", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("agent_run", sa.Column("max_iterations", sa.Integer(), nullable=True))
    op.add_column(
        "agent_run",
        sa.Column("iterations_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("agent_run", sa.Column("finish_reason", sa.String(length=64), nullable=True))
    op.add_column("agent_run", sa.Column("idempotency_key", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE agent_run AS ar
        SET tenant_id = s.tenant_id
        FROM node_run nr
        JOIN flow_run fr ON fr.flow_run_id = nr.flow_run_id
        JOIN session s ON s.session_id = fr.session_id
        WHERE nr.node_run_id = ar.node_run_id
        """
    )
    op.execute(
        """
        UPDATE agent_run AS ar
        SET agent_id = av.agent_id
        FROM agent_version av
        WHERE av.agent_version_id = ar.agent_version_id
        """
    )
    op.execute("DELETE FROM agent_run WHERE tenant_id IS NULL OR agent_id IS NULL")

    op.alter_column("agent_run", "tenant_id", nullable=False)
    op.alter_column("agent_run", "agent_id", nullable=False)
    op.alter_column("agent_run", "node_run_id", nullable=True)

    op.create_foreign_key(
        "fk_agent_run_tenant_id_tenant",
        "agent_run",
        "tenant",
        ["tenant_id"],
        ["tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agent_run_agent_id_agent",
        "agent_run",
        "agent",
        ["agent_id"],
        ["agent_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agent_run_parent_agent_run_id_agent_run",
        "agent_run",
        "agent_run",
        ["parent_agent_run_id"],
        ["agent_run_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agent_run_tenant_id_created_at", "agent_run", ["tenant_id", "created_at"])
    op.create_index("ix_agent_run_root_agent_run_id", "agent_run", ["root_agent_run_id"])
    op.create_index("ix_agent_run_parent_agent_run_id", "agent_run", ["parent_agent_run_id"])
    op.create_index("ix_agent_run_agent_id", "agent_run", ["agent_id"])

    op.add_column("tool_run", sa.Column("tool_call_id", sa.String(length=128), nullable=True))

    op.create_table(
        "agent_run_message",
        sa.Column("agent_run_message_id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("message_sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("tool_calls", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("trust_level", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("provenance", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name="fk_agent_run_message_agent_run_id_agent_run",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "agent_run_id", "message_sequence", name="uq_agent_run_message_sequence"
        ),
    )

    op.create_table(
        "agent_run_event",
        sa.Column("agent_run_event_id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("event_sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("correlation_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name="fk_agent_run_event_agent_run_id_agent_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name="fk_agent_run_event_tenant_id_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("agent_run_id", "event_sequence", name="uq_agent_run_event_sequence"),
    )
    op.create_index(
        "ix_agent_run_event_tenant_id_occurred_at",
        "agent_run_event",
        ["tenant_id", "occurred_at"],
    )

    op.create_table(
        "agent_run_artifact",
        sa.Column("agent_run_artifact_id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name="fk_agent_run_artifact_agent_run_id_agent_run",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("agent_run_id", "artifact_index", name="uq_agent_run_artifact_index"),
    )

    op.create_table(
        "agent_delegation",
        sa.Column("agent_delegation_id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("parent_agent_run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("child_agent_run_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("target_agent_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("transport", sa.String(length=32), nullable=False, server_default="internal"),
        sa.Column("remote_endpoint", sa.Text(), nullable=True),
        sa.Column("a2a_task_id", sa.String(length=128), nullable=False),
        sa.Column("a2a_context_id", sa.String(length=128), nullable=False),
        sa.Column(
            "a2a_task_state", sa.String(length=32), nullable=False, server_default="submitted"
        ),
        sa.Column(
            "request_message", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name="fk_agent_delegation_tenant_id_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_agent_run_id"],
            ["agent_run.agent_run_id"],
            name="fk_agent_delegation_parent_agent_run_id_agent_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["child_agent_run_id"],
            ["agent_run.agent_run_id"],
            name="fk_agent_delegation_child_agent_run_id_agent_run",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_agent_id"],
            ["agent.agent_id"],
            name="fk_agent_delegation_target_agent_id_agent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "a2a_task_id", name="uq_agent_delegation_a2a_task"),
    )
    op.create_index(
        "ix_agent_delegation_parent_agent_run_id", "agent_delegation", ["parent_agent_run_id"]
    )
    op.create_index("ix_agent_delegation_a2a_context_id", "agent_delegation", ["a2a_context_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_delegation_a2a_context_id", table_name="agent_delegation")
    op.drop_index("ix_agent_delegation_parent_agent_run_id", table_name="agent_delegation")
    op.drop_table("agent_delegation")
    op.drop_table("agent_run_artifact")
    op.drop_index("ix_agent_run_event_tenant_id_occurred_at", table_name="agent_run_event")
    op.drop_table("agent_run_event")
    op.drop_table("agent_run_message")

    op.drop_column("tool_run", "tool_call_id")

    op.drop_index("ix_agent_run_agent_id", table_name="agent_run")
    op.drop_index("ix_agent_run_parent_agent_run_id", table_name="agent_run")
    op.drop_index("ix_agent_run_root_agent_run_id", table_name="agent_run")
    op.drop_index("ix_agent_run_tenant_id_created_at", table_name="agent_run")
    op.drop_constraint(
        "fk_agent_run_parent_agent_run_id_agent_run", "agent_run", type_="foreignkey"
    )
    op.drop_constraint("fk_agent_run_agent_id_agent", "agent_run", type_="foreignkey")
    op.drop_constraint("fk_agent_run_tenant_id_tenant", "agent_run", type_="foreignkey")

    op.execute("DELETE FROM agent_run WHERE node_run_id IS NULL")
    op.alter_column("agent_run", "node_run_id", nullable=False)

    op.drop_column("agent_run", "idempotency_key")
    op.drop_column("agent_run", "finish_reason")
    op.drop_column("agent_run", "iterations_used")
    op.drop_column("agent_run", "max_iterations")
    op.drop_column("agent_run", "tool_grant")
    op.drop_column("agent_run", "context_snapshot")
    op.drop_column("agent_run", "delegation_depth")
    op.drop_column("agent_run", "root_agent_run_id")
    op.drop_column("agent_run", "parent_agent_run_id")
    op.drop_column("agent_run", "origin")
    op.drop_column("agent_run", "agent_id")
    op.drop_column("agent_run", "tenant_id")
