from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class FlowVersion(ORMBaseModel):
    __tablename__ = "flow_version"

    flow_version_id = uuid_pk()
    flow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow.flow_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)

    # Compatibilidade declarada: mínimo de AgentVersion aceito
    min_agent_version_major = Column(Integer, nullable=True)
    min_agent_version_minor = Column(Integer, nullable=True)
    min_agent_version_patch = Column(Integer, nullable=True)
    is_active = Column(Boolean(), nullable=False, server_default="false")
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activated_by_principal_id = Column(String(length=128), nullable=True)
    justification = Column(String(length=512), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "flow_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_flow_version_semver",
        ),
        Index("ix_flow_version_status", "status"),
    )
