from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class NodeAgentBinding(ORMBaseModel):
    __tablename__ = "node_agent_binding"

    node_agent_binding_id = uuid_pk()
    node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_version.agent_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
