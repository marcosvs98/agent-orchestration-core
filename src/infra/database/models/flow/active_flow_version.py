from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class ActiveFlowVersion(ORMBaseModel):
    __tablename__ = "active_flow_version"

    flow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow.flow_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flow_graph_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_graph_snapshot.flow_graph_snapshot_id", ondelete="RESTRICT"),
        nullable=True,
    )
    activated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_by_principal_id = Column(String(length=128), nullable=False)
    justification = Column(String(length=512), nullable=False)
