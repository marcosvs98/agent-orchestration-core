from sqlalchemy import Column, ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func

from infra.database.models.base import ORMBaseModel, uuid_pk


class Interaction(ORMBaseModel):
    __tablename__ = "interaction"

    interaction_id = uuid_pk()
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("session.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    channel = Column(String(length=64), nullable=False, server_default="http")
    payload = Column(JSONB, nullable=False, server_default="{}")
    headers = Column(JSONB, nullable=False, server_default="{}")
    interaction_metadata = Column(JSONB, nullable=False, server_default="{}")
    external_message_id = Column(String(length=128), nullable=True)
    request_id = Column(String(length=128), nullable=True)
    trace_id = Column(String(length=128), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())