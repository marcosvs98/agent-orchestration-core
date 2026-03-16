"""API parity support for vector stores and node bindings.

Revision ID: c3f6f91f5a6d
Revises: 861cb744f4f0
Create Date: 2026-03-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3f6f91f5a6d"
down_revision: Union[str, Sequence[str], None] = "861cb744f4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vector_store",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_vector_store_tenant_id_tenant"),
        "vector_store",
        "tenant",
        ["tenant_id"],
        ["tenant_id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE vector_store
        SET tenant_id = (
            SELECT tenant_id
            FROM tenant
            ORDER BY created_at ASC
            LIMIT 1
        )
        WHERE tenant_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE vector_store
        SET name = vector_store_id::text
        WHERE name IS NULL
        """
    )
    op.alter_column(
        "vector_store",
        "name",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "vector_store",
        "tenant_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_unique_constraint(
        op.f("uq_vector_store_tenant_name"),
        "vector_store",
        ["tenant_id", "name"],
    )
    op.create_index(
        op.f("ix_vector_store_tenant_id"),
        "vector_store",
        ["tenant_id"],
        unique=False,
    )
    op.create_unique_constraint(
        op.f("uq_node_ai_execution_policy_binding_node_id"),
        "node_ai_execution_policy_binding",
        ["node_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_node_ai_execution_policy_binding_node_id"),
        "node_ai_execution_policy_binding",
        type_="unique",
    )
    op.drop_index(op.f("ix_vector_store_tenant_id"), table_name="vector_store")
    op.drop_constraint(
        op.f("uq_vector_store_tenant_name"),
        "vector_store",
        type_="unique",
    )
    op.alter_column(
        "vector_store",
        "tenant_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "vector_store",
        "name",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.drop_constraint(
        op.f("fk_vector_store_tenant_id_tenant"),
        "vector_store",
        type_="foreignkey",
    )
    op.drop_column("vector_store", "tenant_id")
