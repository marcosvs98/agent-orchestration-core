"""initial schema

Revision ID: 861cb744f4f0
Revises:
Create Date: 2026-01-23 23:06:41.566193

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "861cb744f4f0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "condition_expression",
        sa.Column("condition_expression_id", sa.UUID(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint(
            "condition_expression_id", name=op.f("pk_condition_expression")
        ),
    )
    op.create_table(
        "llm_pricing",
        sa.Column("llm_pricing_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=False),
        sa.Column(
            "unit", sa.String(length=16), server_default="tokens", nullable=False
        ),
        sa.Column(
            "input_cost_per_1k", sa.Numeric(precision=18, scale=6), nullable=False
        ),
        sa.Column(
            "output_cost_per_1k", sa.Numeric(precision=18, scale=6), nullable=False
        ),
        sa.Column(
            "currency", sa.String(length=8), server_default="USD", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("llm_pricing_id", name=op.f("pk_llm_pricing")),
    )
    op.create_table(
        "model",
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("model_id", name=op.f("pk_model")),
        sa.UniqueConstraint("name", name=op.f("uq_model_name")),
    )
    op.create_table(
        "node_prompt",
        sa.Column("prompt_id", sa.UUID(), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("frozen_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
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
        sa.PrimaryKeyConstraint("prompt_id", name=op.f("pk_node_prompt")),
    )
    op.create_table(
        "tenant",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="America/Sao_Paulo",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="BRL", nullable=False
        ),
        sa.Column(
            "language", sa.String(length=10), server_default="pt_BR", nullable=False
        ),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_tenant")),
    )
    op.create_index(
        "uq_tenant_external_id",
        "tenant",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "user_prompt",
        sa.Column("user_prompt_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
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
            name=op.f("fk_user_prompt_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_prompt_id", name=op.f("pk_user_prompt")),
    )
    op.create_index(
        "ix_user_prompt_tenant_id_title",
        "user_prompt",
        ["tenant_id", "title"],
        unique=False,
    )
    op.create_table(
        "end_user",
        sa.Column("end_user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
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
            name=op.f("fk_end_user_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("end_user_id", name=op.f("pk_end_user")),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_end_user_tenant_user"),
    )
    op.create_table(
        "session",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
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
            name=op.f("fk_session_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_session")),
    )
    op.create_index("ix_session_tenant_id", "session", ["tenant_id"], unique=False)
    op.create_index(
        "ix_session_tenant_id_user_id",
        "session",
        ["tenant_id", "user_id"],
        unique=False,
    )
    op.create_table(
        "user_memory_profile",
        sa.Column("user_memory_profile_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.Integer(), server_default="1", nullable=False),
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
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_memory_profile_id", name=op.f("pk_user_memory_profile")
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_user_memory_profile_user"),
    )
    op.create_table(
        "tool",
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("tool_id", name=op.f("pk_tool")),
        sa.UniqueConstraint("name", name=op.f("uq_tool_name")),
    )
    op.create_table(
        "vector_store",
        sa.Column("vector_store_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
            name=op.f("fk_vector_store_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("vector_store_id", name=op.f("pk_vector_store")),
        sa.UniqueConstraint(
            "tenant_id", "name", name=op.f("uq_vector_store_tenant_name")
        ),
    )
    op.create_index(
        op.f("ix_vector_store_tenant_id"),
        "vector_store",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "rag_chunking_rule",
        sa.Column("rag_chunking_rule_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
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
            name=op.f("fk_rag_chunking_rule_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "rag_chunking_rule_id", name=op.f("pk_rag_chunking_rule")
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_rag_chunking_rule_tenant_name",
        ),
    )
    op.create_index(
        op.f("ix_rag_chunking_rule_tenant_id"),
        "rag_chunking_rule",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "access_policy",
        sa.Column("access_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_access_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("access_policy_id", name=op.f("pk_access_policy")),
    )
    op.create_table(
        "agent",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
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
            name=op.f("fk_agent_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("agent_id", name=op.f("pk_agent")),
    )
    op.create_table(
        "ai_execution_policy",
        sa.Column("ai_execution_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            name=op.f("fk_ai_execution_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "ai_execution_policy_id", name=op.f("pk_ai_execution_policy")
        ),
    )
    op.create_table(
        "authoring_event",
        sa.Column("authoring_event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
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
            name=op.f("fk_authoring_event_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("authoring_event_id", name=op.f("pk_authoring_event")),
    )
    op.create_index(
        "ix_authoring_event_tenant_resource_type_occurred_at",
        "authoring_event",
        ["tenant_id", "resource_type", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "billing_policy",
        sa.Column("billing_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_billing_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("billing_policy_id", name=op.f("pk_billing_policy")),
    )
    op.create_table(
        "memory_policy",
        sa.Column("memory_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_memory_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("memory_policy_id", name=op.f("pk_memory_policy")),
    )
    op.create_table(
        "rag_policy",
        sa.Column("rag_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_rag_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("rag_policy_id", name=op.f("pk_rag_policy")),
    )
    op.create_table(
        "execution_limit_policy",
        sa.Column("execution_limit_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_execution_limit_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "execution_limit_policy_id", name=op.f("pk_execution_limit_policy")
        ),
    )
    op.create_table(
        "flow",
        sa.Column("flow_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
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
            name=op.f("fk_flow_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_id", name=op.f("pk_flow")),
    )
    op.create_table(
        "llm_model_mapping",
        sa.Column("llm_model_mapping_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_alias", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_llm_model_mapping_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.model_id"],
            name=op.f("fk_llm_model_mapping_model_id_model"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "llm_model_mapping_id", name=op.f("pk_llm_model_mapping")
        ),
    )
    op.create_table(
        "llm_provider_config",
        sa.Column("llm_provider_config_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="INACTIVE", nullable=False
        ),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("credential_secret_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_llm_provider_config_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "llm_provider_config_id", name=op.f("pk_llm_provider_config")
        ),
    )
    op.create_table(
        "onboarding",
        sa.Column("onboarding_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
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
            name=op.f("fk_onboarding_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("onboarding_id", name=op.f("pk_onboarding")),
    )
    op.create_table(
        "rag_config",
        sa.Column("rag_config_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vector_store_id", sa.UUID(), nullable=False),
        sa.Column("chunking_rule_id", sa.UUID(), nullable=False),
        sa.Column(
            "corpus_kind",
            sa.String(length=32),
            server_default="TENANT_KNOWLEDGE",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            name=op.f("fk_rag_config_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vector_store_id"],
            ["vector_store.vector_store_id"],
            name=op.f("fk_rag_config_vector_store_id_vector_store"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chunking_rule_id"],
            ["rag_chunking_rule.rag_chunking_rule_id"],
            name=op.f("fk_rag_config_chunking_rule_id_rag_chunking_rule"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("rag_config_id", name=op.f("pk_rag_config")),
        sa.UniqueConstraint(
            "tenant_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rag_config_semver",
        ),
    )
    op.create_index("ix_rag_config_status", "rag_config", ["status"], unique=False)
    op.create_table(
        "rag_usage_counter",
        sa.Column("rag_usage_counter_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("rag_config_id", sa.UUID(), nullable=False),
        sa.Column("document_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint(
            "(scope = 'TENANT' AND user_id IS NULL) OR "
            "(scope = 'USER' AND user_id IS NOT NULL)",
            name="ck_rag_usage_counter_scope_user",
        ),
        sa.CheckConstraint(
            "document_count >= 0 AND chunk_count >= 0",
            name="ck_rag_usage_counter_counts_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_rag_usage_counter_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rag_config_id"],
            ["rag_config.rag_config_id"],
            name=op.f("fk_rag_usage_counter_rag_config_id_rag_config"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["end_user.tenant_id", "end_user.user_id"],
            name=op.f("fk_rag_usage_counter_tenant_user_end_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "rag_usage_counter_id", name=op.f("pk_rag_usage_counter")
        ),
    )
    op.create_index(
        "uq_rag_usage_counter_tenant_scope_null_user",
        "rag_usage_counter",
        ["tenant_id", "rag_config_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'TENANT' AND user_id IS NULL"),
    )
    op.create_index(
        "uq_rag_usage_counter_tenant_user_scope",
        "rag_usage_counter",
        ["tenant_id", "user_id", "rag_config_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'USER' AND user_id IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_rag_usage_counter_tenant_id"),
        "rag_usage_counter",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "rag_document",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("doc_type", sa.String(length=128), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column(
            "embedding_status",
            sa.String(length=32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "embedding_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_embedding_error_code", sa.String(length=128), nullable=True),
        sa.Column("embedding_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "rag_config_id",
            sa.UUID(),
            nullable=True,
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
            name=op.f("fk_rag_document_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rag_config_id"],
            ["rag_config.rag_config_id"],
            name=op.f("fk_rag_document_rag_config_id_rag_config"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_rag_document")),
        sa.UniqueConstraint(
            "tenant_id",
            "content_hash",
            name=op.f("uq_rag_document_tenant_id_content_hash"),
        ),
    )
    op.create_index(
        "ix_rag_document_rag_config_id",
        "rag_document",
        ["rag_config_id"],
        unique=False,
    )
    op.create_table(
        "rag_chunk",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_512", Vector(512), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            ["document_id"],
            ["rag_document.document_id"],
            name=op.f("fk_rag_chunk_document_id_rag_document"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_rag_chunk")),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_rag_chunk_document_id_chunk_index",
        ),
    )
    op.create_index(
        "ix_rag_chunk_document_id",
        "rag_chunk",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_rag_chunk_chunk_index",
        "rag_chunk",
        ["chunk_index"],
        unique=False,
    )
    op.create_index(
        "ix_rag_chunk_embedding",
        "rag_chunk",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
    )
    op.create_index(
        "ix_rag_chunk_embedding_512",
        "rag_chunk",
        ["embedding_512"],
        unique=False,
        postgresql_using="ivfflat",
    )
    op.create_table(
        "rag_query_cache",
        sa.Column("query_cache_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("query_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_512", Vector(512), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "use_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_rag_query_cache_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("query_cache_id", name=op.f("pk_rag_query_cache")),
        sa.UniqueConstraint(
            "tenant_id",
            "query_hash",
            name=op.f("uq_rag_query_cache_tenant_id_query_hash"),
        ),
    )
    op.create_table(
        "semantic_answer_cache",
        sa.Column("cache_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("query_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_512", Vector(512), nullable=True),
        sa.Column(
            "response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("model_alias", sa.String(length=128), nullable=True),
        sa.Column("inference_layer", sa.String(length=16), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column(
            "ttl_seconds",
            sa.Integer(),
            server_default="3600",
            nullable=False,
        ),
        sa.Column(
            "hit_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_semantic_answer_cache_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("cache_id", name=op.f("pk_semantic_answer_cache")),
        sa.UniqueConstraint(
            "tenant_id",
            "task_type",
            "query_hash",
            name=op.f("uq_semantic_answer_cache_tenant_task_query"),
        ),
    )
    op.create_index(
        "ix_semantic_answer_cache_embedding",
        "semantic_answer_cache",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
    )
    op.create_index(
        "ix_semantic_answer_cache_embedding_512",
        "semantic_answer_cache",
        ["embedding_512"],
        unique=False,
        postgresql_using="ivfflat",
    )
    op.create_index(
        "ix_semantic_answer_cache_tenant_task_expires_at",
        "semantic_answer_cache",
        ["tenant_id", "task_type", "expires_at"],
        unique=False,
    )
    op.create_table(
        "rate_limit_policy",
        sa.Column("rate_limit_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
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
            name=op.f("fk_rate_limit_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "rate_limit_policy_id", name=op.f("pk_rate_limit_policy")
        ),
    )
    op.create_table(
        "tool_config",
        sa.Column("tool_config_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
            name=op.f("fk_tool_config_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["tool.tool_id"],
            name=op.f("fk_tool_config_tool_id_tool"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tool_config_id", name=op.f("pk_tool_config")),
        sa.UniqueConstraint(
            "tool_id",
            "tenant_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_tool_config_semver",
        ),
    )
    op.create_index("ix_tool_config_status", "tool_config", ["status"], unique=False)
    op.create_index(
        "ix_tool_config_tenant_id_tool_config_id",
        "tool_config",
        ["tenant_id", "tool_config_id"],
        unique=False,
    )
    op.create_table(
        "access_policy_version",
        sa.Column("access_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("access_policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            ["access_policy_id"],
            ["access_policy.access_policy_id"],
            name=op.f("fk_access_policy_version_access_policy_id_access_policy"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "access_policy_version_id", name=op.f("pk_access_policy_version")
        ),
        sa.UniqueConstraint(
            "access_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_access_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_access_policy_version_status",
        "access_policy_version",
        ["status"],
        unique=False,
    )
    op.create_table(
        "ai_execution_policy_version",
        sa.Column("ai_execution_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("ai_execution_policy_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
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
            ["ai_execution_policy_id"],
            ["ai_execution_policy.ai_execution_policy_id"],
            name=op.f(
                "fk_ai_execution_policy_version_ai_execution_policy_id_ai_execution_policy"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model.model_id"],
            name=op.f("fk_ai_execution_policy_version_model_id_model"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "ai_execution_policy_version_id",
            name=op.f("pk_ai_execution_policy_version"),
        ),
        sa.UniqueConstraint(
            "ai_execution_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_ai_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_ai_policy_version_status",
        "ai_execution_policy_version",
        ["status"],
        unique=False,
    )
    op.create_table(
        "billing_policy_version",
        sa.Column("billing_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("billing_policy_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=False),
        sa.Column("version_minor", sa.Integer(), nullable=False),
        sa.Column("version_patch", sa.Integer(), nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("justification", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["billing_policy_id"],
            ["billing_policy.billing_policy_id"],
            name=op.f("fk_billing_policy_version_billing_policy_id_billing_policy"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_billing_policy_version_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "billing_policy_version_id", name=op.f("pk_billing_policy_version")
        ),
    )
    op.create_index(
        "ix_billing_policy_version_active_per_tenant",
        "billing_policy_version",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "execution_limit_policy_version",
        sa.Column("execution_limit_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("execution_limit_policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "max_nodes_per_flow_run", sa.Integer(), server_default="100", nullable=False
        ),
        sa.Column(
            "max_node_runs_per_flow_run",
            sa.Integer(),
            server_default="500",
            nullable=False,
        ),
        sa.Column(
            "max_agent_runs_per_interaction",
            sa.Integer(),
            server_default="100",
            nullable=False,
        ),
        sa.Column(
            "max_tool_runs_per_flow_run",
            sa.Integer(),
            server_default="200",
            nullable=False,
        ),
        sa.Column(
            "max_tokens_per_agent_run",
            sa.Integer(),
            server_default="8192",
            nullable=False,
        ),
        sa.Column(
            "max_total_runtime_seconds",
            sa.Integer(),
            server_default="300",
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
            ["execution_limit_policy_id"],
            ["execution_limit_policy.execution_limit_policy_id"],
            name=op.f(
                "fk_execution_limit_policy_version_execution_limit_policy_id_execution_limit_policy"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "execution_limit_policy_version_id",
            name=op.f("pk_execution_limit_policy_version"),
        ),
        sa.UniqueConstraint(
            "execution_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_execution_limit_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_execution_limit_policy_version_status",
        "execution_limit_policy_version",
        ["status"],
        unique=False,
    )
    op.create_table(
        "memory_policy_version",
        sa.Column("memory_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("memory_policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "retention_ttl_seconds",
            sa.Integer(),
            server_default="2592000",
            nullable=False,
        ),
        sa.Column(
            "consent_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_schemas",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
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
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("justification", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["memory_policy_id"],
            ["memory_policy.memory_policy_id"],
            name=op.f("fk_memory_policy_version_memory_policy_id_memory_policy"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_memory_policy_version_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "memory_policy_version_id", name=op.f("pk_memory_policy_version")
        ),
        sa.UniqueConstraint(
            "memory_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_memory_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_memory_policy_version_status",
        "memory_policy_version",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_memory_policy_version_active_per_tenant",
        "memory_policy_version",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "rag_policy_version",
        sa.Column("rag_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("rag_policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "policy_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("justification", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["rag_policy_id"],
            ["rag_policy.rag_policy_id"],
            name=op.f("fk_rag_policy_version_rag_policy_id_rag_policy"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_rag_policy_version_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "rag_policy_version_id", name=op.f("pk_rag_policy_version")
        ),
        sa.UniqueConstraint(
            "rag_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rag_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_rag_policy_version_status",
        "rag_policy_version",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_rag_policy_version_active_per_tenant",
        "rag_policy_version",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "flow_version",
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("flow_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("min_agent_version_major", sa.Integer(), nullable=True),
        sa.Column("min_agent_version_minor", sa.Integer(), nullable=True),
        sa.Column("min_agent_version_patch", sa.Integer(), nullable=True),
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
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("justification", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["flow_id"],
            ["flow.flow_id"],
            name=op.f("fk_flow_version_flow_id_flow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("flow_version_id", name=op.f("pk_flow_version")),
        sa.UniqueConstraint(
            "flow_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_flow_version_semver",
        ),
    )
    op.create_index("ix_flow_version_status", "flow_version", ["status"], unique=False)
    op.create_index(
        "ix_flow_version_active_per_flow",
        "flow_version",
        ["flow_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "flow_graph_snapshot",
        sa.Column("flow_graph_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("graph_hash", sa.String(length=128), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "compiled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("compiled_by", sa.String(length=128), nullable=False),
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
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_graph_snapshot_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "flow_graph_snapshot_id", name=op.f("pk_flow_graph_snapshot")
        ),
        sa.UniqueConstraint(
            "flow_version_id", name=op.f("uq_flow_graph_snapshot_flow_version_id")
        ),
        sa.UniqueConstraint(
            "graph_hash", name=op.f("uq_flow_graph_snapshot_graph_hash")
        ),
    )
    op.create_table(
        "interaction",
        sa.Column("interaction_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=True),
        sa.Column("result_node_run_id", sa.UUID(), nullable=True),
        sa.Column(
            "channel", sa.String(length=64), server_default="http", nullable=False
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "interaction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["session_id"],
            ["session.session_id"],
            name=op.f("fk_interaction_session_id_session"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("interaction_id", name=op.f("pk_interaction")),
    )
    op.create_index(
        "ix_interaction_session_id_received_at",
        "interaction",
        ["session_id", "received_at"],
        unique=False,
    )
    op.create_table(
        "flow_run",
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("origin_flow_run_id", sa.UUID(), nullable=True),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("interaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), server_default="CREATED", nullable=False
        ),
        sa.Column(
            "canonical_status",
            sa.String(length=32),
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiting_reason", sa.String(length=255), nullable=True),
        sa.Column("waiting_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("flow_graph_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("flow_deployment_id", sa.UUID(), nullable=True),
        sa.Column(
            "runtime_contract",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("execution_plan_hash", sa.String(length=128), nullable=True),
        sa.Column("runtime_policy_hash", sa.String(length=128), nullable=True),
        sa.Column("tool_catalog_hash", sa.String(length=128), nullable=True),
        sa.Column("llm_provider_config_hash", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.UUID(), nullable=True),
        sa.Column("root_observation_id", sa.String(length=128), nullable=True),
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
            ["flow_graph_snapshot_id"],
            ["flow_graph_snapshot.flow_graph_snapshot_id"],
            name=op.f("fk_flow_run_flow_graph_snapshot_id_flow_graph_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_run_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["interaction_id"],
            ["interaction.interaction_id"],
            name=op.f("fk_flow_run_interaction_id_interaction"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["origin_flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_flow_run_origin_flow_run_id_flow_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.session_id"],
            name=op.f("fk_flow_run_session_id_session"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_run_id", name=op.f("pk_flow_run")),
    )
    op.create_foreign_key(
        "fk_interaction_flow_run_id_flow_run",
        "interaction",
        "flow_run",
        ["flow_run_id"],
        ["flow_run_id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "flow_run_lock",
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.UUID(), nullable=True),
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_flow_run_lock_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("flow_run_id", name=op.f("pk_flow_run_lock")),
    )
    op.create_table(
        "response_artifact",
        sa.Column("response_artifact_id", sa.UUID(), nullable=False),
        sa.Column("interaction_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_response_artifact_flow_run_id_flow_run"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["interaction_id"],
            ["interaction.interaction_id"],
            name=op.f("fk_response_artifact_interaction_id_interaction"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "response_artifact_id", name=op.f("pk_response_artifact")
        ),
    )
    op.create_table(
        "execution_event",
        sa.Column("execution_event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("causation_id", sa.UUID(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("node_id", sa.UUID(), nullable=True),
        sa.Column("edge_id", sa.String(length=128), nullable=True),
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_execution_event_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.session_id"],
            name=op.f("fk_execution_event_session_id_session"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_execution_event_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("execution_event_id", name=op.f("pk_execution_event")),
    )
    op.create_index(
        "ix_execution_event_tenant_user_occurred_at",
        "execution_event",
        ["tenant_id", "user_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_event_tenant_flow_run_occurred_at",
        "execution_event",
        ["tenant_id", "flow_run_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_event_tenant_session_occurred_at",
        "execution_event",
        ["tenant_id", "session_id", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "onboarding_version",
        sa.Column("onboarding_version_id", sa.UUID(), nullable=False),
        sa.Column("onboarding_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
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
            ["onboarding_id"],
            ["onboarding.onboarding_id"],
            name=op.f("fk_onboarding_version_onboarding_id_onboarding"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "onboarding_version_id", name=op.f("pk_onboarding_version")
        ),
        sa.UniqueConstraint(
            "onboarding_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_onboarding_version_semver",
        ),
    )
    op.create_index(
        "ix_onboarding_version_status", "onboarding_version", ["status"], unique=False
    )
    op.create_table(
        "rate_limit_policy_version",
        sa.Column("rate_limit_policy_version_id", sa.UUID(), nullable=False),
        sa.Column("rate_limit_policy_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
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
            ["rate_limit_policy_id"],
            ["rate_limit_policy.rate_limit_policy_id"],
            name=op.f(
                "fk_rate_limit_policy_version_rate_limit_policy_id_rate_limit_policy"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "rate_limit_policy_version_id", name=op.f("pk_rate_limit_policy_version")
        ),
        sa.UniqueConstraint(
            "rate_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_rate_limit_policy_version_semver",
        ),
    )
    op.create_index(
        "ix_rate_limit_policy_version_action",
        "rate_limit_policy_version",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_rate_limit_policy_version_status",
        "rate_limit_policy_version",
        ["status"],
        unique=False,
    )
    op.create_table(
        "runtime_policy",
        sa.Column("runtime_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("flow_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.String(length=16), server_default="1", nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column(
            "policy_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flow_id"],
            ["flow.flow_id"],
            name=op.f("fk_runtime_policy_flow_id_flow"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_runtime_policy_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("runtime_policy_id", name=op.f("pk_runtime_policy")),
    )
    op.create_table(
        "agent_version",
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("ai_execution_policy_version_id", sa.UUID(), nullable=True),
        sa.Column("rag_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), server_default="DRAFT", nullable=False
        ),
        sa.Column("version_major", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_patch", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("supported_tool_schema_version", sa.Integer(), nullable=True),
        sa.Column(
            "supported_tool_config_hash_prefix", sa.String(length=128), nullable=True
        ),
        sa.Column(
            "persona_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("system_prompt", sa.Text(), nullable=True),
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
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=True),
        sa.Column("justification", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.agent_id"],
            name=op.f("fk_agent_version_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ai_execution_policy_version_id"],
            ["ai_execution_policy_version.ai_execution_policy_version_id"],
            name=op.f(
                "fk_agent_version_ai_execution_policy_version_id_ai_execution_policy_version"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rag_config_id"],
            ["rag_config.rag_config_id"],
            name=op.f("fk_agent_version_rag_config_id_rag_config"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("agent_version_id", name=op.f("pk_agent_version")),
        sa.UniqueConstraint(
            "agent_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_agent_version_semver",
        ),
    )
    op.create_index(
        "ix_agent_version_status", "agent_version", ["status"], unique=False
    )
    op.create_index(
        "ix_agent_version_active_per_agent",
        "agent_version",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "flow_graph",
        sa.Column("flow_graph_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_graph_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_graph_id", name=op.f("pk_flow_graph")),
        sa.UniqueConstraint(
            "flow_version_id", name=op.f("uq_flow_graph_flow_version_id")
        ),
    )
    op.create_table(
        "flow_graph_draft",
        sa.Column("flow_graph_draft_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "status", sa.String(length=32), server_default="DRAFT", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_by", sa.String(length=128), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_graph_draft_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "flow_graph_draft_id", name=op.f("pk_flow_graph_draft")
        ),
        sa.UniqueConstraint(
            "flow_version_id", name=op.f("uq_flow_graph_draft_flow_version_id")
        ),
    )
    op.create_table(
        "node_template",
        sa.Column("node_template_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("node_type", sa.String(length=128), nullable=False),
        sa.Column(
            "default_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "scope", sa.String(length=32), nullable=False, server_default="system"
        ),
        sa.Column("owner_tenant_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
            ["owner_tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_node_template_owner_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("node_template_id", name=op.f("pk_node_template")),
        sa.UniqueConstraint("code", name=op.f("uq_node_template_code")),
    )
    op.create_table(
        "node",
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("node_prompt_id", sa.UUID(), nullable=False),
        sa.Column(
            "allow_rag_tenant", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "allow_user_memory_structured",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "allow_user_memory_vector",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("rag_config_id", sa.UUID(), nullable=True),
        sa.Column(
            "allow_session_context",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "allow_memory_write", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("node_type", sa.String(length=128), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("source_node_template_id", sa.UUID(), nullable=True),
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
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_node_flow_version_id_flow_version"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_prompt_id"],
            ["node_prompt.prompt_id"],
            name=op.f("fk_node_node_prompt_id_node_prompt"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_node_template_id"],
            ["node_template.node_template_id"],
            name=op.f("fk_node_source_node_template_id_node_template"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["rag_config_id"],
            ["rag_config.rag_config_id"],
            name=op.f("fk_node_rag_config_id_rag_config"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("node_id", name=op.f("pk_node")),
    )
    op.create_table(
        "onboarding_run",
        sa.Column("onboarding_run_id", sa.UUID(), nullable=False),
        sa.Column("onboarding_version_id", sa.UUID(), nullable=False),
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
            ["onboarding_version_id"],
            ["onboarding_version.onboarding_version_id"],
            name=op.f("fk_onboarding_run_onboarding_version_id_onboarding_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("onboarding_run_id", name=op.f("pk_onboarding_run")),
    )
    op.create_table(
        "onboarding_step",
        sa.Column("onboarding_step_id", sa.UUID(), nullable=False),
        sa.Column("onboarding_version_id", sa.UUID(), nullable=False),
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
            ["onboarding_version_id"],
            ["onboarding_version.onboarding_version_id"],
            name=op.f("fk_onboarding_step_onboarding_version_id_onboarding_version"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("onboarding_step_id", name=op.f("pk_onboarding_step")),
    )
    op.create_table(
        "agent_version_tool_binding",
        sa.Column("agent_version_tool_binding_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("tool_config_id", sa.UUID(), nullable=False),
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
            ["agent_version_id"],
            ["agent_version.agent_version_id"],
            name=op.f("fk_agent_version_tool_binding_agent_version_id_agent_version"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_config_id"],
            ["tool_config.tool_config_id"],
            name=op.f("fk_agent_version_tool_binding_tool_config_id_tool_config"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "agent_version_tool_binding_id", name=op.f("pk_agent_version_tool_binding")
        ),
    )
    op.create_index(
        "ix_agent_version_tool_binding_agent_version_id",
        "agent_version_tool_binding",
        ["agent_version_id"],
        unique=False,
    )
    op.create_table(
        "node_agent_binding",
        sa.Column("node_agent_binding_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
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
            ["agent_version_id"],
            ["agent_version.agent_version_id"],
            name=op.f("fk_node_agent_binding_agent_version_id_agent_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["node.node_id"],
            name=op.f("fk_node_agent_binding_node_id_node"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "node_agent_binding_id", name=op.f("pk_node_agent_binding")
        ),
    )
    op.create_index(
        "ix_node_agent_binding_node_id",
        "node_agent_binding",
        ["node_id"],
        unique=False,
    )
    op.create_table(
        "node_ai_execution_policy_binding",
        sa.Column("node_ai_execution_policy_binding_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("ai_execution_policy_version_id", sa.UUID(), nullable=False),
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
            ["ai_execution_policy_version_id"],
            ["ai_execution_policy_version.ai_execution_policy_version_id"],
            name=op.f(
                "fk_node_ai_execution_policy_binding_ai_execution_policy_version_id_ai_execution_policy_version"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["node.node_id"],
            name=op.f("fk_node_ai_execution_policy_binding_node_id_node"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "node_ai_execution_policy_binding_id",
            name=op.f("pk_node_ai_execution_policy_binding"),
        ),
    )
    op.create_unique_constraint(
        op.f("uq_node_ai_execution_policy_binding_node_id"),
        "node_ai_execution_policy_binding",
        ["node_id"],
    )
    op.create_table(
        "node_run",
        sa.Column("node_run_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="CREATED", nullable=False
        ),
        sa.Column(
            "canonical_status",
            sa.String(length=32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_node_run_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["node.node_id"],
            name=op.f("fk_node_run_node_id_node"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("node_run_id", name=op.f("pk_node_run")),
    )
    op.create_foreign_key(
        op.f("fk_interaction_result_node_run_id_node_run"),
        "interaction",
        "node_run",
        ["result_node_run_id"],
        ["node_run_id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "human_sla_policy",
        sa.Column("human_sla_policy_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("fallback_reason", sa.String(length=64), nullable=False),
        sa.Column("initial_priority", sa.String(length=32), nullable=False),
        sa.Column("target_response_hours", sa.Integer(), nullable=True),
        sa.Column("target_resolution_hours", sa.Integer(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            name=op.f("fk_human_sla_policy_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "human_sla_policy_id", name=op.f("pk_human_sla_policy")
        ),
        sa.CheckConstraint(
            "target_response_hours IS NULL OR target_response_hours > 0",
            name="ck_human_sla_policy_target_response_hours_positive",
        ),
        sa.CheckConstraint(
            "target_resolution_hours IS NULL OR target_resolution_hours > 0",
            name="ck_human_sla_policy_target_resolution_hours_positive",
        ),
    )
    op.create_index(
        "ix_human_sla_policy_tenant_node_reason",
        "human_sla_policy",
        ["tenant_id", "node", "fallback_reason"],
        unique=False,
    )
    op.create_table(
        "human_sla_escalation_rule",
        sa.Column("human_sla_escalation_rule_id", sa.UUID(), nullable=False),
        sa.Column("human_sla_policy_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("trigger_after_hours", sa.Integer(), nullable=False),
        sa.Column("new_priority", sa.String(length=32), nullable=False),
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
            ["human_sla_policy_id"],
            ["human_sla_policy.human_sla_policy_id"],
            name=op.f(
                "fk_human_sla_escalation_rule_human_sla_policy_id_human_sla_policy"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "human_sla_escalation_rule_id",
            name=op.f("pk_human_sla_escalation_rule"),
        ),
        sa.UniqueConstraint(
            "human_sla_policy_id",
            "level",
            name="uq_human_sla_escalation_rule_policy_level",
        ),
        sa.CheckConstraint(
            "level >= 0",
            name="ck_human_sla_escalation_rule_level_non_neg",
        ),
        sa.CheckConstraint(
            "trigger_after_hours >= 0",
            name="ck_human_sla_escalation_rule_trigger_non_neg",
        ),
    )
    op.create_table(
        "sla_case",
        sa.Column("sla_case_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("node_run_id", sa.UUID(), nullable=False),
        sa.Column("interaction_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("fallback_reason", sa.Text(), nullable=False),
        sa.Column("human_agent_id", sa.String(length=128), nullable=True),
        sa.Column("resolution_status", sa.String(length=32), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("human_sla_policy_id", sa.UUID(), nullable=True),
        sa.Column(
            "current_escalation_level",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_target_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sla_breached",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name="fk_sla_case_flow_run_id_flow_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["interaction_id"],
            ["interaction.interaction_id"],
            name="fk_sla_case_interaction_id_interaction",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_run.node_run_id"],
            name="fk_sla_case_node_run_id_node_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.session_id"],
            name="fk_sla_case_session_id_session",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name="fk_sla_case_tenant_id_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["human_sla_policy_id"],
            ["human_sla_policy.human_sla_policy_id"],
            name=op.f("fk_sla_case_human_sla_policy_id_human_sla_policy"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("sla_case_id", name="pk_sla_case"),
        sa.UniqueConstraint(
            "flow_run_id",
            "node_run_id",
            name="uq_sla_case_flow_run_node_run",
        ),
        sa.CheckConstraint(
            "current_escalation_level >= 0",
            name="ck_sla_case_current_escalation_level_non_neg",
        ),
    )
    op.create_index(
        op.f("ix_sla_case_human_sla_policy_id"),
        "sla_case",
        ["human_sla_policy_id"],
        unique=False,
    )
    op.create_index(
        "ix_sla_case_tenant_status",
        "sla_case",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index("ix_sla_case_session", "sla_case", ["session_id"], unique=False)
    op.create_index("ix_sla_case_flow_run", "sla_case", ["flow_run_id"], unique=False)
    op.create_index("ix_sla_case_opened_at", "sla_case", ["opened_at"], unique=False)
    op.create_index(
        "ix_sla_case_sla_target_at",
        "sla_case",
        ["sla_target_at"],
        unique=False,
    )
    op.create_table(
        "router",
        sa.Column("router_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
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
            ["node_id"],
            ["node.node_id"],
            name=op.f("fk_router_node_id_node"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("router_id", name=op.f("pk_router")),
    )
    op.create_table(
        "step_run",
        sa.Column("step_run_id", sa.UUID(), nullable=False),
        sa.Column("onboarding_step_id", sa.UUID(), nullable=False),
        sa.Column("onboarding_run_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="PENDING", nullable=False
        ),
        sa.Column(
            "input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "output_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("schema_id", sa.UUID(), nullable=True),
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
            ["onboarding_run_id"],
            ["onboarding_run.onboarding_run_id"],
            name=op.f("fk_step_run_onboarding_run_id_onboarding_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["onboarding_step_id"],
            ["onboarding_step.onboarding_step_id"],
            name=op.f("fk_step_run_onboarding_step_id_onboarding_step"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("step_run_id", name=op.f("pk_step_run")),
    )
    op.create_index(
        "ix_step_run_onboarding_run_id", "step_run", ["onboarding_run_id"], unique=False
    )
    op.create_index("ix_step_run_status", "step_run", ["status"], unique=False)
    op.create_table(
        "agent_run",
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("node_run_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("billing_policy_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), server_default="CREATED", nullable=False
        ),
        sa.Column(
            "canonical_status",
            sa.String(length=32),
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("system_prompt_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "runtime_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("runtime_snapshot_hash", sa.String(length=64), nullable=True),
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
            ["agent_version_id"],
            ["agent_version.agent_version_id"],
            name=op.f("fk_agent_run_agent_version_id_agent_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["billing_policy_version_id"],
            ["billing_policy_version.billing_policy_version_id"],
            name=op.f("fk_agent_run_billing_policy_version_id_billing_policy_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_run.node_run_id"],
            name=op.f("fk_agent_run_node_run_id_node_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_run_id", name=op.f("pk_agent_run")),
    )
    op.create_table(
        "graph_state",
        sa.Column("graph_state_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("last_node_run_id", sa.UUID(), nullable=True),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_graph_state_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_node_run_id"],
            ["node_run.node_run_id"],
            name=op.f("fk_graph_state_last_node_run_id_node_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("graph_state_id", name=op.f("pk_graph_state")),
    )
    op.create_table(
        "routing_rule",
        sa.Column("routing_rule_id", sa.UUID(), nullable=False),
        sa.Column("router_id", sa.UUID(), nullable=False),
        sa.Column("condition_expression_id", sa.UUID(), nullable=False),
        sa.Column("from_node_id", sa.UUID(), nullable=False),
        sa.Column("to_node_id", sa.UUID(), nullable=False),
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
            ["condition_expression_id"],
            ["condition_expression.condition_expression_id"],
            name=op.f("fk_routing_rule_condition_expression_id_condition_expression"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_node_id"],
            ["node.node_id"],
            name=op.f("fk_routing_rule_from_node_id_node"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["router_id"],
            ["router.router_id"],
            name=op.f("fk_routing_rule_router_id_router"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_node_id"],
            ["node.node_id"],
            name=op.f("fk_routing_rule_to_node_id_node"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("routing_rule_id", name=op.f("pk_routing_rule")),
    )
    op.create_table(
        "tool_run",
        sa.Column("tool_run_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("node_run_id", sa.UUID(), nullable=True),
        sa.Column("tool_config_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="CREATED", nullable=False
        ),
        sa.Column(
            "canonical_status",
            sa.String(length=32),
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "input",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "has_side_effect", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("estimated_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("billing_policy_version_id", sa.UUID(), nullable=True),
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
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name=op.f("fk_tool_run_agent_run_id_agent_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["billing_policy_version_id"],
            ["billing_policy_version.billing_policy_version_id"],
            name=op.f("fk_tool_run_billing_policy_version_id_billing_policy_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_run.node_run_id"],
            name=op.f("fk_tool_run_node_run_id_node_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_config_id"],
            ["tool_config.tool_config_id"],
            name=op.f("fk_tool_run_tool_config_id_tool_config"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("tool_run_id", name=op.f("pk_tool_run")),
    )
    op.create_table(
        "run_failure",
        sa.Column("run_failure_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=True),
        sa.Column("node_run_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("tool_run_id", sa.UUID(), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=False),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
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
            ["agent_run_id"],
            ["agent_run.agent_run_id"],
            name=op.f("fk_run_failure_agent_run_id_agent_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_run_failure_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_run.node_run_id"],
            name=op.f("fk_run_failure_node_run_id_node_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_run_id"],
            ["tool_run.tool_run_id"],
            name=op.f("fk_run_failure_tool_run_id_tool_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_failure_id", name=op.f("pk_run_failure")),
    )
    op.create_index(
        "ix_llm_pricing_provider_model_status",
        "llm_pricing",
        ["provider", "provider_model", "status"],
        unique=False,
    )
    op.create_index(
        "ix_llm_model_mapping_tenant_provider_alias_status",
        "llm_model_mapping",
        ["tenant_id", "provider", "model_alias", "status"],
        unique=False,
    )
    op.create_index(
        "ix_llm_provider_config_tenant_provider_status",
        "llm_provider_config",
        ["tenant_id", "provider", "status"],
        unique=False,
    )
    op.create_index(
        "ix_graph_state_flow_run_id",
        "graph_state",
        ["flow_run_id"],
        unique=False,
    )
    op.create_table(
        "mcp_server",
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "config_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("flow_deployment_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            name=op.f("fk_mcp_server_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("mcp_server_id", name=op.f("pk_mcp_server")),
    )
    op.create_index(
        "ix_mcp_server_tenant_id",
        "mcp_server",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "mcp_server_tool",
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("tool_config_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.mcp_server_id"],
            name=op.f("fk_mcp_server_tool_mcp_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_config_id"],
            ["tool_config.tool_config_id"],
            name=op.f("fk_mcp_server_tool_tool_config_id_tool_config"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "mcp_server_id",
            "tool_config_id",
            name=op.f("pk_mcp_server_tool"),
        ),
    )
    op.create_table(
        "mcp_server_vector_store",
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("vector_store_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.mcp_server_id"],
            name=op.f("fk_mcp_server_vector_store_mcp_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vector_store_id"],
            ["vector_store.vector_store_id"],
            name=op.f("fk_mcp_server_vector_store_vector_store_id_vector_store"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "mcp_server_id",
            "vector_store_id",
            name=op.f("pk_mcp_server_vector_store"),
        ),
    )
    op.create_table(
        "mcp_server_user_prompt",
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("user_prompt_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.mcp_server_id"],
            name=op.f("fk_mcp_server_user_prompt_mcp_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_prompt_id"],
            ["user_prompt.user_prompt_id"],
            name=op.f("fk_mcp_server_user_prompt_user_prompt_id_user_prompt"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "mcp_server_id",
            "user_prompt_id",
            name=op.f("pk_mcp_server_user_prompt"),
        ),
    )
    op.create_table(
        "mcp_server_credential",
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.mcp_server_id"],
            name=op.f("fk_mcp_server_credential_mcp_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("credential_id", name=op.f("pk_mcp_server_credential")),
    )
    op.create_index(
        "ix_mcp_server_credential_mcp_server_id",
        "mcp_server_credential",
        ["mcp_server_id"],
        unique=False,
    )
    op.create_index(
        "uq_mcp_credential_active_per_server",
        "mcp_server_credential",
        ["mcp_server_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "flow_snapshot",
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "snapshot_schema_version", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("frozen_rag_config_id", sa.UUID(), nullable=True),
        sa.Column("frozen_rag_chunking_rule_id", sa.UUID(), nullable=True),
        sa.Column("frozen_rag_policy_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "frozen_rag_materialization_hash", sa.String(length=64), nullable=True
        ),
        sa.Column(
            "runtime_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tool_catalog",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("llm_provider_config_hash", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
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
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_snapshot_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_snapshot_id", name=op.f("pk_flow_snapshot")),
        sa.UniqueConstraint(
            "flow_version_id", name=op.f("uq_flow_snapshot_flow_version_id")
        ),
        sa.UniqueConstraint(
            "snapshot_hash", name=op.f("uq_flow_snapshot_snapshot_hash")
        ),
    )
    op.create_table(
        "snapshot_effective_policy",
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
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
            ["flow_snapshot_id"],
            ["flow_snapshot.flow_snapshot_id"],
            name=op.f("fk_snapshot_effective_policy_flow_snapshot_id_flow_snapshot"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "flow_snapshot_id", name=op.f("pk_snapshot_effective_policy")
        ),
    )
    op.create_table(
        "snapshot_binding",
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("binding_key", sa.String(length=128), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            ["flow_snapshot_id"],
            ["flow_snapshot.flow_snapshot_id"],
            name=op.f("fk_snapshot_binding_flow_snapshot_id_flow_snapshot"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "flow_snapshot_id", "binding_key", name=op.f("pk_snapshot_binding")
        ),
    )
    op.create_table(
        "flow_deployment",
        sa.Column("flow_deployment_id", sa.UUID(), nullable=False),
        sa.Column("flow_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("flow_snapshot_id", sa.UUID(), nullable=False),
        sa.Column(
            "environment",
            sa.String(length=64),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("deployed_by", sa.String(length=128), nullable=False),
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
            ["flow_id"],
            ["flow.flow_id"],
            name=op.f("fk_flow_deployment_flow_id_flow"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_flow_deployment_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_snapshot_id"],
            ["flow_snapshot.flow_snapshot_id"],
            name=op.f("fk_flow_deployment_flow_snapshot_id_flow_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_deployment_id", name=op.f("pk_flow_deployment")),
        sa.UniqueConstraint(
            "flow_id", "environment", "status", name="uq_flow_deployment_slot"
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("flow_deployment")
    op.drop_table("snapshot_binding")
    op.drop_table("snapshot_effective_policy")
    op.drop_table("flow_snapshot")
    op.drop_index(
        "uq_mcp_credential_active_per_server",
        table_name="mcp_server_credential",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_index(
        "ix_mcp_server_credential_mcp_server_id",
        table_name="mcp_server_credential",
    )
    op.drop_table("mcp_server_credential")
    op.drop_table("mcp_server_user_prompt")
    op.drop_table("mcp_server_vector_store")
    op.drop_table("mcp_server_tool")
    op.drop_index("ix_mcp_server_tenant_id", table_name="mcp_server")
    op.drop_table("mcp_server")
    op.drop_index("ix_graph_state_flow_run_id", table_name="graph_state")
    op.drop_index(
        "ix_llm_provider_config_tenant_provider_status",
        table_name="llm_provider_config",
    )
    op.drop_index(
        "ix_llm_model_mapping_tenant_provider_alias_status",
        table_name="llm_model_mapping",
    )
    op.drop_index(
        "ix_llm_pricing_provider_model_status",
        table_name="llm_pricing",
    )
    op.drop_table("run_failure")
    op.drop_table("tool_run")
    op.drop_table("routing_rule")
    op.drop_table("graph_state")
    op.drop_table("agent_run")
    op.drop_index("ix_sla_case_sla_target_at", table_name="sla_case")
    op.drop_index("ix_sla_case_opened_at", table_name="sla_case")
    op.drop_index("ix_sla_case_flow_run", table_name="sla_case")
    op.drop_index("ix_sla_case_session", table_name="sla_case")
    op.drop_index(op.f("ix_sla_case_human_sla_policy_id"), table_name="sla_case")
    op.drop_index("ix_sla_case_tenant_status", table_name="sla_case")
    op.drop_table("sla_case")
    op.drop_table("human_sla_escalation_rule")
    op.drop_index(
        "ix_human_sla_policy_tenant_node_reason",
        table_name="human_sla_policy",
    )
    op.drop_table("human_sla_policy")
    op.drop_index("ix_step_run_status", table_name="step_run")
    op.drop_index("ix_step_run_onboarding_run_id", table_name="step_run")
    op.drop_table("step_run")
    op.drop_table("router")
    op.drop_constraint(
        op.f("fk_interaction_result_node_run_id_node_run"),
        "interaction",
        type_="foreignkey",
    )
    op.drop_table("node_run")
    op.drop_constraint(
        op.f("uq_node_ai_execution_policy_binding_node_id"),
        "node_ai_execution_policy_binding",
        type_="unique",
    )
    op.drop_table("node_ai_execution_policy_binding")
    op.drop_index(
        "ix_node_agent_binding_node_id",
        table_name="node_agent_binding",
    )
    op.drop_table("node_agent_binding")
    op.drop_index(
        "ix_agent_version_tool_binding_agent_version_id",
        table_name="agent_version_tool_binding",
    )
    op.drop_table("agent_version_tool_binding")
    op.drop_table("onboarding_step")
    op.drop_table("onboarding_run")
    op.drop_table("node")
    op.drop_table("flow_graph_snapshot")
    op.drop_table("flow_graph_draft")
    op.drop_table("flow_graph")
    op.drop_index(
        "ix_agent_version_active_per_agent",
        table_name="agent_version",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_agent_version_status", table_name="agent_version")
    op.drop_table("agent_version")
    op.drop_table("runtime_policy")
    op.drop_index(
        "ix_rag_policy_version_active_per_tenant",
        table_name="rag_policy_version",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_rag_policy_version_status", table_name="rag_policy_version")
    op.drop_table("rag_policy_version")
    op.drop_index(
        "ix_memory_policy_version_active_per_tenant",
        table_name="memory_policy_version",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_memory_policy_version_status", table_name="memory_policy_version")
    op.drop_table("memory_policy_version")
    op.drop_index(
        "ix_rate_limit_policy_version_status", table_name="rate_limit_policy_version"
    )
    op.drop_index(
        "ix_rate_limit_policy_version_action", table_name="rate_limit_policy_version"
    )
    op.drop_table("rate_limit_policy_version")
    op.drop_index("ix_onboarding_version_status", table_name="onboarding_version")
    op.drop_table("onboarding_version")
    op.drop_index(
        "ix_flow_version_active_per_flow",
        table_name="flow_version",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_index("ix_flow_version_status", table_name="flow_version")
    op.drop_table("flow_version")
    op.drop_index(
        "ix_execution_limit_policy_version_status",
        table_name="execution_limit_policy_version",
    )
    op.drop_table("execution_limit_policy_version")
    op.drop_index(
        "ix_execution_event_tenant_session_occurred_at",
        table_name="execution_event",
    )
    op.drop_index(
        "ix_execution_event_tenant_flow_run_occurred_at",
        table_name="execution_event",
    )
    op.drop_index(
        "ix_execution_event_tenant_user_occurred_at", table_name="execution_event"
    )
    op.drop_table("execution_event")
    op.drop_index(
        "ix_billing_policy_version_active_per_tenant",
        table_name="billing_policy_version",
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_table("billing_policy_version")
    op.drop_index(
        "ix_ai_policy_version_status", table_name="ai_execution_policy_version"
    )
    op.drop_table("ai_execution_policy_version")
    op.drop_index("ix_access_policy_version_status", table_name="access_policy_version")
    op.drop_table("access_policy_version")
    op.drop_index(
        "ix_authoring_event_tenant_resource_type_occurred_at",
        table_name="authoring_event",
    )
    op.drop_index(
        "ix_tool_config_tenant_id_tool_config_id",
        table_name="tool_config",
    )
    op.drop_index("ix_tool_config_status", table_name="tool_config")
    op.drop_table("tool_config")
    op.drop_table("user_memory_profile")
    op.drop_index("ix_session_tenant_id_user_id", table_name="session")
    op.drop_index("ix_session_tenant_id", table_name="session")
    op.drop_table("session")
    op.drop_table("end_user")
    op.drop_table("response_artifact")
    op.drop_table("rate_limit_policy")
    op.drop_table("rag_query_cache")
    op.drop_index(
        "ix_semantic_answer_cache_embedding_512",
        table_name="semantic_answer_cache",
    )
    op.drop_index("ix_rag_chunk_embedding_512", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_embedding", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_chunk_index", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_document_id", table_name="rag_chunk")
    op.drop_table("rag_chunk")
    op.drop_table("rag_document")
    op.drop_index(
        op.f("ix_rag_usage_counter_tenant_id"), table_name="rag_usage_counter"
    )
    op.drop_index(
        "uq_rag_usage_counter_tenant_user_scope",
        table_name="rag_usage_counter",
        postgresql_where=sa.text("scope = 'USER' AND user_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_rag_usage_counter_tenant_scope_null_user",
        table_name="rag_usage_counter",
        postgresql_where=sa.text("scope = 'TENANT' AND user_id IS NULL"),
    )
    op.drop_table("rag_usage_counter")
    op.drop_index("ix_rag_config_status", table_name="rag_config")
    op.drop_table("rag_config")
    op.drop_index(
        op.f("ix_rag_chunking_rule_tenant_id"), table_name="rag_chunking_rule"
    )
    op.drop_table("rag_chunking_rule")
    op.drop_table("onboarding")
    op.drop_table("llm_provider_config")
    op.drop_table("llm_model_mapping")
    op.drop_table("flow_run_lock")
    op.drop_table("flow")
    op.drop_table("execution_limit_policy")
    op.drop_table("rag_policy")
    op.drop_table("memory_policy")
    op.drop_table("billing_policy")
    op.drop_table("authoring_event")
    op.drop_table("ai_execution_policy")
    op.drop_table("agent")
    op.drop_table("access_policy")
    op.drop_table("vector_store")
    op.drop_table("tool")
    op.drop_index("ix_user_prompt_tenant_id_title", table_name="user_prompt")
    op.drop_table("user_prompt")
    op.drop_index(
        "uq_tenant_external_id",
        table_name="tenant",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_table("tenant")
    op.drop_table("node_prompt")
    op.drop_table("model")
    op.drop_table("llm_pricing")
    op.drop_index("ix_interaction_session_id_received_at", table_name="interaction")
    op.drop_table("interaction")
    op.drop_table("flow_run")
    op.drop_table("condition_expression")
    # ### end Alembic commands ###
