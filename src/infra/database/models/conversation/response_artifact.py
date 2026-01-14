from sqlalchemy import Column, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class ResponseArtifact(ORMBaseModel):
    __tablename__ = "response_artifact"

    response_artifact_id = uuid_pk()
    interaction_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interaction.interaction_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="RESTRICT"),
        nullable=False,
    )
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    schema_version = Column(Integer, nullable=False, server_default="1")
