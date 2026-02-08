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
        "ai_task",
        sa.Column("ai_task_id", sa.UUID(), nullable=False),
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
        sa.PrimaryKeyConstraint("ai_task_id", name=op.f("pk_ai_task")),
        sa.UniqueConstraint("name", name=op.f("uq_ai_task_name")),
    )
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
        sa.Column("input_schema_id", sa.String(length=128), nullable=True),
        sa.Column("output_schema_id", sa.String(length=128), nullable=True),
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
        "system_prompt_template",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "allowed_placeholders",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="DRAFT", nullable=False
        ),
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
        sa.PrimaryKeyConstraint("template_id", name=op.f("pk_system_prompt_template")),
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
        "session",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
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
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_session")),
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
        sa.PrimaryKeyConstraint("vector_store_id", name=op.f("pk_vector_store")),
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
        "escalation_policy",
        sa.Column("escalation_policy_id", sa.UUID(), nullable=False),
        sa.Column("condition_expression_id", sa.UUID(), nullable=True),
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
            name=op.f(
                "fk_escalation_policy_condition_expression_id_condition_expression"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "escalation_policy_id", name=op.f("pk_escalation_policy")
        ),
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
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("credential_secret_ref", sa.String(length=255), nullable=True),
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
        "rag_document",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("doc_type", sa.String(length=128), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
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
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_rag_document_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_rag_document")),
        sa.UniqueConstraint(
            "tenant_id",
            "content_hash",
            name=op.f("uq_rag_document_tenant_id_content_hash"),
        ),
    )
    op.create_table(
        "rag_chunk",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
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
    op.create_table(
        "rag_query_cache",
        sa.Column("query_cache_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("query_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["billing_policy_id"],
            ["billing_policy.billing_policy_id"],
            name=op.f("fk_billing_policy_version_billing_policy_id_billing_policy"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "billing_policy_version_id", name=op.f("pk_billing_policy_version")
        ),
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
    op.create_table(
        "flow_run",
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("origin_flow_run_id", sa.UUID(), nullable=True),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
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
        "escalation",
        sa.Column("escalation_id", sa.UUID(), nullable=False),
        sa.Column("flow_run_id", sa.UUID(), nullable=False),
        sa.Column("escalation_policy_id", sa.UUID(), nullable=False),
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
            ["escalation_policy_id"],
            ["escalation_policy.escalation_policy_id"],
            name=op.f("fk_escalation_escalation_policy_id_escalation_policy"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.flow_run_id"],
            name=op.f("fk_escalation_flow_run_id_flow_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("escalation_id", name=op.f("pk_escalation")),
    )
    op.create_table(
        "execution_event",
        sa.Column("execution_event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
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
        sa.Column("type", sa.String(length=64), nullable=False),
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
        "active_billing_policy_version",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("billing_policy_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
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
            ["billing_policy_version_id"],
            ["billing_policy_version.billing_policy_version_id"],
            name=op.f(
                "fk_active_billing_policy_version_billing_policy_version_id_billing_policy_version"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_active_billing_policy_version_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", name=op.f("pk_active_billing_policy_version")
        ),
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
        sa.Column("system_prompt_template_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["system_prompt_template_id"],
            ["system_prompt_template.template_id"],
            name=op.f(
                "fk_agent_version_system_prompt_template_id_system_prompt_template"
            ),
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
        "node",
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("ai_task_id", sa.UUID(), nullable=True),
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
            ["ai_task_id"],
            ["ai_task.ai_task_id"],
            name=op.f("fk_node_ai_task_id_ai_task"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_node_flow_version_id_flow_version"),
            ondelete="CASCADE",
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
        "active_agent_version",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
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
            ["agent_id"],
            ["agent.agent_id"],
            name=op.f("fk_active_agent_version_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_version.agent_version_id"],
            name=op.f("fk_active_agent_version_agent_version_id_agent_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("agent_id", name=op.f("pk_active_agent_version")),
    )
    op.create_table(
        "active_flow_version",
        sa.Column("flow_id", sa.UUID(), nullable=False),
        sa.Column("flow_version_id", sa.UUID(), nullable=False),
        sa.Column("flow_graph_snapshot_id", sa.UUID(), nullable=True),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_by_principal_id", sa.String(length=128), nullable=False),
        sa.Column("justification", sa.String(length=512), nullable=False),
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
            name=op.f(
                "fk_active_flow_version_flow_graph_snapshot_id_flow_graph_snapshot"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["flow_id"],
            ["flow.flow_id"],
            name=op.f("fk_active_flow_version_flow_id_flow"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["flow_version_id"],
            ["flow_version.flow_version_id"],
            name=op.f("fk_active_flow_version_flow_version_id_flow_version"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("flow_id", name=op.f("pk_active_flow_version")),
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
        sa.Column("ai_task_id", sa.UUID(), nullable=True),
        sa.Column("node_run_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("ai_execution_policy_version_id", sa.UUID(), nullable=False),
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
            ["ai_execution_policy_version_id"],
            ["ai_execution_policy_version.ai_execution_policy_version_id"],
            name=op.f(
                "fk_agent_run_ai_execution_policy_version_id_ai_execution_policy_version"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_task_id"],
            ["ai_task.ai_task_id"],
            name=op.f("fk_agent_run_ai_task_id_ai_task"),
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
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("run_failure")
    op.drop_table("tool_run")
    op.drop_table("routing_rule")
    op.drop_table("graph_state")
    op.drop_table("agent_run")
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
    op.drop_table("node_ai_execution_policy_binding")
    op.drop_table("node_agent_binding")
    op.drop_table("agent_version_tool_binding")
    op.drop_table("active_flow_version")
    op.drop_table("active_agent_version")
    op.drop_table("onboarding_step")
    op.drop_table("onboarding_run")
    op.drop_table("node")
    op.drop_table("flow_graph_snapshot")
    op.drop_table("flow_graph_draft")
    op.drop_table("flow_graph")
    op.drop_index("ix_agent_version_status", table_name="agent_version")
    op.drop_table("agent_version")
    op.drop_table("active_billing_policy_version")
    op.drop_table("runtime_policy")
    op.drop_index(
        "ix_rate_limit_policy_version_status", table_name="rate_limit_policy_version"
    )
    op.drop_index(
        "ix_rate_limit_policy_version_action", table_name="rate_limit_policy_version"
    )
    op.drop_table("rate_limit_policy_version")
    op.drop_index("ix_onboarding_version_status", table_name="onboarding_version")
    op.drop_table("onboarding_version")
    op.drop_index("ix_flow_version_status", table_name="flow_version")
    op.drop_table("flow_version")
    op.drop_index(
        "ix_execution_limit_policy_version_status",
        table_name="execution_limit_policy_version",
    )
    op.drop_table("execution_limit_policy_version")
    op.drop_table("execution_event")
    op.drop_table("escalation")
    op.drop_table("billing_policy_version")
    op.drop_index(
        "ix_ai_policy_version_status", table_name="ai_execution_policy_version"
    )
    op.drop_table("ai_execution_policy_version")
    op.drop_index("ix_access_policy_version_status", table_name="access_policy_version")
    op.drop_table("access_policy_version")
    op.drop_index("ix_tool_config_status", table_name="tool_config")
    op.drop_table("tool_config")
    op.drop_table("session")
    op.drop_table("response_artifact")
    op.drop_table("rate_limit_policy")
    op.drop_table("rag_query_cache")
    op.drop_index("ix_rag_chunk_embedding", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_chunk_index", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_document_id", table_name="rag_chunk")
    op.drop_table("rag_chunk")
    op.drop_table("rag_document")
    op.drop_index("ix_rag_config_status", table_name="rag_config")
    op.drop_table("rag_config")
    op.drop_table("onboarding")
    op.drop_table("llm_provider_config")
    op.drop_table("llm_model_mapping")
    op.drop_table("flow_run_lock")
    op.drop_table("flow")
    op.drop_table("execution_limit_policy")
    op.drop_table("escalation_policy")
    op.drop_table("billing_policy")
    op.drop_table("authoring_event")
    op.drop_table("ai_execution_policy")
    op.drop_table("agent")
    op.drop_table("access_policy")
    op.drop_table("vector_store")
    op.drop_table("tool")
    op.drop_index(
        "uq_tenant_external_id",
        table_name="tenant",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_table("tenant")
    op.drop_table("system_prompt_template")
    op.drop_table("node_prompt")
    op.drop_table("model")
    op.drop_table("llm_pricing")
    op.drop_table("interaction")
    op.drop_table("flow_run")
    op.drop_table("condition_expression")
    op.drop_table("ai_task")
    # ### end Alembic commands ###
