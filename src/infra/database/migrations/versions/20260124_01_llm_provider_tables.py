"""Planning 24 - LLM provider configuration, model mapping, and pricing tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260124_01_llm_provider_tables"
down_revision: Union[str, None] = "20260122_02_execution_event_canonical_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    numeric = sa.Numeric(18, 6)

    op.create_table(
        "llm_provider_config",
        sa.Column("llm_provider_config_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="INACTIVE"),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("credential_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index(
        "ix_llm_provider_config_active",
        "llm_provider_config",
        ["tenant_id", "provider"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "llm_model_mapping",
        sa.Column("llm_model_mapping_id", uuid, primary_key=True, nullable=False),
        sa.Column("tenant_id", uuid, sa.ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_alias", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index(
        "ix_llm_model_mapping_active",
        "llm_model_mapping",
        ["tenant_id", "provider", "model_alias"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "llm_pricing",
        sa.Column("llm_pricing_id", uuid, primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="tokens"),
        sa.Column("input_cost_per_1k", numeric, nullable=False),
        sa.Column("output_cost_per_1k", numeric, nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
    )
    op.create_index(
        "ix_llm_pricing_active",
        "llm_pricing",
        ["provider", "provider_model"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("ix_llm_pricing_active", table_name="llm_pricing")
    op.drop_table("llm_pricing")
    op.drop_index("ix_llm_model_mapping_active", table_name="llm_model_mapping")
    op.drop_table("llm_model_mapping")
    op.drop_index("ix_llm_provider_config_active", table_name="llm_provider_config")
    op.drop_table("llm_provider_config")
