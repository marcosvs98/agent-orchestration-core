from sqlalchemy import Column, Text

from infra.database.models.base import ORMBaseModel, uuid_pk


class ConditionExpression(ORMBaseModel):
    __tablename__ = "condition_expression"

    condition_expression_id = uuid_pk()
    expression = Column(Text(), nullable=True)
