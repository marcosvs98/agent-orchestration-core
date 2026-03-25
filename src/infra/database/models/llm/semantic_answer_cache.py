from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from infra.database.models.base import ORMBaseModel, uuid_pk


class SemanticAnswerCache(ORMBaseModel):
    __tablename__ = "semantic_answer_cache"

    cache_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_type = Column(String(length=64), nullable=False)
    query_hash = Column(String(length=128), nullable=False)
    embedding = Column(Vector(), nullable=True)
    response_json = Column(JSONB, nullable=False)
    model_alias = Column(String(length=128), nullable=True)
    inference_layer = Column(String(length=16), nullable=False)
    similarity_score = Column(Float, nullable=True)
    ttl_seconds = Column(Integer, nullable=False, server_default="3600")
    hit_count = Column(Integer, nullable=False, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_hit_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "task_type",
            "query_hash",
            name="uq_semantic_answer_cache_tenant_task_query",
        ),
    )
