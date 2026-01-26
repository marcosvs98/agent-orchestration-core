from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from infra.database.models.base import ORMBaseModel, uuid_pk


class ToolConfig(ORMBaseModel):
    __tablename__ = "tool_config"

    tool_config_id = uuid_pk()
    tool_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool.tool_id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)
    schema_version = Column(Integer, nullable=True)
    config = Column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        UniqueConstraint(
            "tool_id",
            "tenant_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_tool_config_semver",
        ),
        Index("ix_tool_config_status", "status"),
    )
