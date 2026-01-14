from sqlalchemy import Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class GraphState(ORMBaseModel):
    __tablename__ = "graph_state"

    graph_state_id = uuid_pk()
    flow_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flow_run.flow_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    last_node_run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node_run.node_run_id", ondelete="SET NULL"),
        nullable=True,
    )
    state = Column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
