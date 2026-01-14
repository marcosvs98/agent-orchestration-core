"""AI governance guardrails and AgentRun audit fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260113_01_ai_governance"
down_revision = "20260112_05_run_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_run",
        sa.Column("ai_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_task.ai_task_id", ondelete="RESTRICT"), nullable=True),
    )
    op.add_column(
        "agent_run",
        sa.Column("model", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "agent_run",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_run",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_run",
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_run", "estimated_cost")
    op.drop_column("agent_run", "output_tokens")
    op.drop_column("agent_run", "input_tokens")
    op.drop_column("agent_run", "model")
    op.drop_column("agent_run", "ai_task_id")
