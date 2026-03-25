from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Node(ORMBaseModel):
    __tablename__ = "node"

    node_id = uuid_pk()
    flow_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_version.flow_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    node_prompt_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_prompt.prompt_id", ondelete="RESTRICT"),
        nullable=False,
    )
    allow_rag_tenant = Column(Boolean, nullable=False, server_default="false")
    allow_user_memory_structured = Column(
        Boolean, nullable=False, server_default="false"
    )
    allow_user_memory_vector = Column(Boolean, nullable=False, server_default="false")
    rag_config_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_config.rag_config_id", ondelete="SET NULL"),
        nullable=True,
    )
    allow_session_context = Column(Boolean, nullable=False, server_default="false")
    allow_memory_write = Column(Boolean, nullable=False, server_default="false")
    node_type = Column(String(length=128), nullable=True)
    config = Column(JSONB, nullable=True)
    source_node_template_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_template.node_template_id", ondelete="SET NULL"),
        nullable=True,
    )
