from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class SnapshotBinding(ORMBaseModel):
    __tablename__ = "snapshot_binding"

    flow_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_snapshot.flow_snapshot_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    binding_key = Column(String(length=128), primary_key=True, nullable=False)
    value_type = Column(String(length=32), nullable=False)
    source_kind = Column(String(length=32), nullable=False)
    value = Column(JSONB, nullable=False)
