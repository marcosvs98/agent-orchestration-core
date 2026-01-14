from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class Router(ORMBaseModel):
    __tablename__ = "router"

    router_id = uuid_pk()
    node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="CASCADE"),
        nullable=False,
    )
