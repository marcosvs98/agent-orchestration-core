from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class FlowGraph(ORMBaseModel):
    __tablename__ = "flow_graph"

    flow_graph_id = uuid_pk()
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    definition = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(length=128), nullable=False)
