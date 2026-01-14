"""Planning (13) execution_event evidence record (denormalized + deterministic ordering)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260113_03_execution_event"
down_revision: Union[str, None] = "20260113_02_planning12_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.add_column("execution_event", sa.Column("tenant_id", uuid, nullable=True))
    op.add_column("execution_event", sa.Column("session_id", uuid, nullable=True))
    op.add_column("execution_event", sa.Column("causation_id", uuid, nullable=True))
    op.add_column(
        "execution_event",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.add_column("execution_event", sa.Column("event_sequence", sa.BigInteger(), nullable=True))
    op.add_column(
        "execution_event",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Backfill tenant_id/session_id and occurred_at from flow_run/session. Use created_at as occurred_at baseline.
    op.execute(
        """
        UPDATE execution_event e
        SET session_id = fr.session_id,
            tenant_id = s.tenant_id,
            occurred_at = COALESCE(e.occurred_at, e.created_at)
        FROM flow_run fr
        JOIN session s ON s.session_id = fr.session_id
        WHERE e.flow_run_id = fr.flow_run_id
        """
    )

    # Backfill event_sequence deterministically per flow_run_id using created_at ordering.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                e.execution_event_id,
                ROW_NUMBER() OVER (
                    PARTITION BY e.flow_run_id
                    ORDER BY e.created_at ASC, e.execution_event_id ASC
                ) AS seq
            FROM execution_event e
        )
        UPDATE execution_event e
        SET event_sequence = ranked.seq
        FROM ranked
        WHERE e.execution_event_id = ranked.execution_event_id
        """
    )

    op.alter_column("execution_event", "tenant_id", nullable=False)
    op.alter_column("execution_event", "session_id", nullable=False)
    op.alter_column("execution_event", "occurred_at", nullable=False)
    op.alter_column("execution_event", "event_sequence", nullable=False)

    op.create_index("ix_execution_event_flow_run_id_seq", "execution_event", ["flow_run_id", "event_sequence"])
    op.create_index("ix_execution_event_tenant_id", "execution_event", ["tenant_id"])
    op.create_index("ix_execution_event_session_id", "execution_event", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_event_session_id", table_name="execution_event")
    op.drop_index("ix_execution_event_tenant_id", table_name="execution_event")
    op.drop_index("ix_execution_event_flow_run_id_seq", table_name="execution_event")

    op.drop_column("execution_event", "schema_version")
    op.drop_column("execution_event", "event_sequence")
    op.drop_column("execution_event", "occurred_at")
    op.drop_column("execution_event", "causation_id")
    op.drop_column("execution_event", "session_id")
    op.drop_column("execution_event", "tenant_id")
