"""Planning 26 - flow_run root observation identifiers."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260126_01_langfuse_flow_run_fields"
down_revision: Union[str, None] = "20260124_01_llm_provider_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flow_run",
        sa.Column("root_observation_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_flow_run_root_observation_id",
        "flow_run",
        ["root_observation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_flow_run_root_observation_id", table_name="flow_run")
    op.drop_column("flow_run", "root_observation_id")
