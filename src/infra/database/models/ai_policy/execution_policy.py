from infra.database.models.base import ORMBaseModel, uuid_pk


class AIExecutionPolicy(ORMBaseModel):
    __tablename__ = "ai_execution_policy"

    ai_execution_policy_id = uuid_pk()
