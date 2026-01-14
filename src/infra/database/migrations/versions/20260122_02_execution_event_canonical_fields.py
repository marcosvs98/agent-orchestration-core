"""Planning 22 - execution_event canonical fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260122_02_execution_event_canonical_fields"
down_revision: Union[str, None] = "20260122_01_flow_run_frozen_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.add_column("execution_event", sa.Column("node_id", uuid, nullable=True))
    op.add_column("execution_event", sa.Column("edge_id", sa.String(length=128), nullable=True))

    op.create_index(
        "ix_execution_event_flow_run_id_occurred_at",
        "execution_event",
        ["flow_run_id", "occurred_at"],
        unique=False,
    )
    op.create_index("ix_execution_event_type", "execution_event", ["type"], unique=False)
    op.create_index("ix_execution_event_node_id", "execution_event", ["node_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_execution_event_node_id", table_name="execution_event")
    op.drop_index("ix_execution_event_type", table_name="execution_event")
    op.drop_index("ix_execution_event_flow_run_id_occurred_at", table_name="execution_event")

    op.drop_column("execution_event", "edge_id")
    op.drop_column("execution_event", "node_id")
