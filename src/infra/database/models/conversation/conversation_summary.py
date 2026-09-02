from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class ConversationSummary(ORMBaseModel):
    """Durable carry-forward for a provider-side conversation.

    The provider holds the transcript; this row holds what must survive rolling it over or losing
    the Redis mapping. Without it, a mapping expiry silently discarded the whole conversation.
    """

    __tablename__ = "conversation_summary"

    conversation_summary_id = uuid_pk()
    tenant_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_key = Column(String(length=255), nullable=False)
    session_id = Column(PG_UUID(as_uuid=True), nullable=True)
    summary_text = Column(Text, nullable=False)
    turns_covered = Column(Integer, nullable=False, server_default="0")
    estimated_tokens_covered = Column(Integer, nullable=False, server_default="0")
    provider_conversation_id = Column(String(length=128), nullable=True)
    rollover_count = Column(Integer, nullable=False, server_default="0")
    last_rolled_over_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_key", name="uq_conversation_summary_conversation_key"),
    )
