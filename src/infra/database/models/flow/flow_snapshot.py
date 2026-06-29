from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class FlowSnapshot(ORMBaseModel):
    __tablename__ = "flow_snapshot"

    flow_snapshot_id = uuid_pk()
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    snapshot_schema_version = Column(Integer, nullable=False, server_default="1")
    snapshot_hash = Column(String(length=64), nullable=False, unique=True)
    snapshot = Column(JSONB, nullable=False)
    frozen_rag_config_id = Column(PG_UUID(as_uuid=True), nullable=True)
    frozen_rag_chunking_rule_id = Column(PG_UUID(as_uuid=True), nullable=True)
    frozen_rag_policy_version_id = Column(PG_UUID(as_uuid=True), nullable=True)
    frozen_rag_materialization_hash = Column(String(length=64), nullable=True)
    runtime_policy = Column(JSONB, nullable=False, server_default="{}")
    tool_catalog = Column(JSONB, nullable=False, server_default="{}")
    llm_provider_config_hash = Column(String(length=128), nullable=True)
    created_by = Column(String(length=128), nullable=False)
