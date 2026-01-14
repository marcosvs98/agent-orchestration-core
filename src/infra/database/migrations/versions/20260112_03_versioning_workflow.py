"""Version workflow fields, semver, config_hash, compatibility (inline columns)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260112_03_versioning_workflow"
down_revision: Union[str, None] = "20260112_02_execution_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FlowVersion
    op.add_column("flow_version", sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False))
    op.add_column("flow_version", sa.Column("version_major", sa.Integer(), server_default="1", nullable=False))
    op.add_column("flow_version", sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False))
    op.add_column("flow_version", sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False))
    op.add_column("flow_version", sa.Column("config_hash", sa.String(length=128), nullable=True))
    op.add_column("flow_version", sa.Column("min_agent_version_major", sa.Integer(), nullable=True))
    op.add_column("flow_version", sa.Column("min_agent_version_minor", sa.Integer(), nullable=True))
    op.add_column("flow_version", sa.Column("min_agent_version_patch", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_flow_version_semver",
        "flow_version",
        ["flow_id", "version_major", "version_minor", "version_patch"],
    )
    op.create_index("ix_flow_version_status", "flow_version", ["status"])

    # AgentVersion
    op.add_column("agent_version", sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False))
    op.add_column("agent_version", sa.Column("version_major", sa.Integer(), server_default="1", nullable=False))
    op.add_column("agent_version", sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_version", sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_version", sa.Column("config_hash", sa.String(length=128), nullable=True))
    op.add_column("agent_version", sa.Column("supported_tool_schema_version", sa.Integer(), nullable=True))
    op.add_column("agent_version", sa.Column("supported_tool_config_hash_prefix", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_agent_version_semver",
        "agent_version",
        ["agent_id", "version_major", "version_minor", "version_patch"],
    )
    op.create_index("ix_agent_version_status", "agent_version", ["status"])

    # AIExecutionPolicyVersion
    op.add_column("ai_execution_policy_version", sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False))
    op.add_column("ai_execution_policy_version", sa.Column("version_major", sa.Integer(), server_default="1", nullable=False))
    op.add_column("ai_execution_policy_version", sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ai_execution_policy_version", sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ai_execution_policy_version", sa.Column("config_hash", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_ai_policy_version_semver",
        "ai_execution_policy_version",
        ["ai_execution_policy_id", "version_major", "version_minor", "version_patch"],
    )
    op.create_index("ix_ai_policy_version_status", "ai_execution_policy_version", ["status"])

    # ToolConfig (tratado como versão)
    op.add_column("tool_config", sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False))
    op.add_column("tool_config", sa.Column("version_major", sa.Integer(), server_default="1", nullable=False))
    op.add_column("tool_config", sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False))
    op.add_column("tool_config", sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False))
    op.add_column("tool_config", sa.Column("config_hash", sa.String(length=128), nullable=True))
    op.add_column("tool_config", sa.Column("schema_version", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_tool_config_semver",
        "tool_config",
        ["tool_id", "tenant_id", "version_major", "version_minor", "version_patch"],
    )
    op.create_index("ix_tool_config_status", "tool_config", ["status"])

    # RagConfig (append-only por tenant)
    op.add_column("rag_config", sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False))
    op.add_column("rag_config", sa.Column("version_major", sa.Integer(), server_default="1", nullable=False))
    op.add_column("rag_config", sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False))
    op.add_column("rag_config", sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False))
    op.add_column("rag_config", sa.Column("config_hash", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_rag_config_semver",
        "rag_config",
        ["tenant_id", "version_major", "version_minor", "version_patch"],
    )
    op.create_index("ix_rag_config_status", "rag_config", ["status"])


def downgrade() -> None:
    # RagConfig
    op.drop_index("ix_rag_config_status", table_name="rag_config")
    op.drop_constraint("uq_rag_config_semver", "rag_config", type_="unique")
    op.drop_column("rag_config", "config_hash")
    op.drop_column("rag_config", "version_patch")
    op.drop_column("rag_config", "version_minor")
    op.drop_column("rag_config", "version_major")
    op.drop_column("rag_config", "status")

    # ToolConfig
    op.drop_index("ix_tool_config_status", table_name="tool_config")
    op.drop_constraint("uq_tool_config_semver", "tool_config", type_="unique")
    op.drop_column("tool_config", "schema_version")
    op.drop_column("tool_config", "config_hash")
    op.drop_column("tool_config", "version_patch")
    op.drop_column("tool_config", "version_minor")
    op.drop_column("tool_config", "version_major")
    op.drop_column("tool_config", "status")

    # AIExecutionPolicyVersion
    op.drop_index("ix_ai_policy_version_status", table_name="ai_execution_policy_version")
    op.drop_constraint("uq_ai_policy_version_semver", "ai_execution_policy_version", type_="unique")
    op.drop_column("ai_execution_policy_version", "config_hash")
    op.drop_column("ai_execution_policy_version", "version_patch")
    op.drop_column("ai_execution_policy_version", "version_minor")
    op.drop_column("ai_execution_policy_version", "version_major")
    op.drop_column("ai_execution_policy_version", "status")

    # AgentVersion
    op.drop_index("ix_agent_version_status", table_name="agent_version")
    op.drop_constraint("uq_agent_version_semver", "agent_version", type_="unique")
    op.drop_column("agent_version", "supported_tool_config_hash_prefix")
    op.drop_column("agent_version", "supported_tool_schema_version")
    op.drop_column("agent_version", "config_hash")
    op.drop_column("agent_version", "version_patch")
    op.drop_column("agent_version", "version_minor")
    op.drop_column("agent_version", "version_major")
    op.drop_column("agent_version", "status")

    # FlowVersion
    op.drop_index("ix_flow_version_status", table_name="flow_version")
    op.drop_constraint("uq_flow_version_semver", "flow_version", type_="unique")
    op.drop_column("flow_version", "min_agent_version_patch")
    op.drop_column("flow_version", "min_agent_version_minor")
    op.drop_column("flow_version", "min_agent_version_major")
    op.drop_column("flow_version", "config_hash")
    op.drop_column("flow_version", "version_patch")
    op.drop_column("flow_version", "version_minor")
    op.drop_column("flow_version", "version_major")
    op.drop_column("flow_version", "status")
