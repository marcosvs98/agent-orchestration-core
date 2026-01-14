from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel


class FlowRunLock(ORMBaseModel):
    __tablename__ = "flow_run_lock"

    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    locked_at = Column(DateTime(timezone=True), nullable=False)
    owner = Column(String(length=128), nullable=True)
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=True)
