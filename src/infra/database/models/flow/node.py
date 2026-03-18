from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Node(ORMBaseModel):
    __tablename__ = "node"

    node_id = uuid_pk()
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_task_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_task.ai_task_id", ondelete="RESTRICT"),
        nullable=True,
    )
    node_type = Column(String(length=128), nullable=True)
    config = Column(JSONB, nullable=True)
    source_node_template_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_template.node_template_id", ondelete="SET NULL"),
        nullable=True,
    )
