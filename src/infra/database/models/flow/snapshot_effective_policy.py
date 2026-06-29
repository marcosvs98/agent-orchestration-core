from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class SnapshotEffectivePolicy(ORMBaseModel):
    __tablename__ = "snapshot_effective_policy"

    flow_snapshot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_snapshot.flow_snapshot_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    policy_hash = Column(String(length=64), nullable=False)
    definition = Column(JSONB, nullable=False)
