from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class NodeAIExecutionPolicyBinding(ORMBaseModel):
    __tablename__ = "node_ai_execution_policy_binding"

    node_ai_execution_policy_binding_id = uuid_pk()
    node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_execution_policy_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "ai_execution_policy_version.ai_execution_policy_version_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("node_id", name="uq_node_ai_execution_policy_binding_node_id"),
    )
