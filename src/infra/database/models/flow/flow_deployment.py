from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class FlowDeployment(ORMBaseModel):
    __tablename__ = "flow_deployment"

    flow_deployment_id = uuid_pk()
    flow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow.flow_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flow_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_snapshot.flow_snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    environment = Column(String(length=64), nullable=False, server_default="default")
    status = Column(String(length=16), nullable=False, server_default="ACTIVE")
    deployed_by = Column(String(length=128), nullable=False)

    __table_args__ = (
        Index(
            "uq_flow_deployment_active_slot",
            "flow_id",
            "environment",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
