from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class RoutingRule(ORMBaseModel):
    __tablename__ = "routing_rule"

    routing_rule_id = uuid_pk()
    router_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("router.router_id", ondelete="CASCADE"),
        nullable=False,
    )
    condition_expression_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("condition_expression.condition_expression_id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="RESTRICT"),
        nullable=False,
    )
    to_node_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("node.node_id", ondelete="RESTRICT"),
        nullable=False,
    )
