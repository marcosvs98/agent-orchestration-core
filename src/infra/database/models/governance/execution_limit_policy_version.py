from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from infra.database.models.base import ORMBaseModel, uuid_pk


class ExecutionLimitPolicyVersion(ORMBaseModel):
    __tablename__ = "execution_limit_policy_version"

    execution_limit_policy_version_id = uuid_pk()
    execution_limit_policy_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("execution_limit_policy.execution_limit_policy_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(length=16), nullable=False, server_default="DRAFT")
    version_major = Column(Integer, nullable=False, server_default="1")
    version_minor = Column(Integer, nullable=False, server_default="0")
    version_patch = Column(Integer, nullable=False, server_default="0")
    config_hash = Column(String(length=128), nullable=True)

    max_nodes_per_flow_run = Column(Integer, nullable=False, server_default="100")
    max_node_runs_per_flow_run = Column(Integer, nullable=False, server_default="500")
    max_agent_runs_per_interaction = Column(Integer, nullable=False, server_default="100")
    max_tool_runs_per_flow_run = Column(Integer, nullable=False, server_default="200")
    max_tokens_per_agent_run = Column(Integer, nullable=False, server_default="8192")
    max_total_runtime_seconds = Column(Integer, nullable=False, server_default="300")

    __table_args__ = (
        UniqueConstraint(
            "execution_limit_policy_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_execution_limit_policy_version_semver",
        ),
        Index("ix_execution_limit_policy_version_status", "status"),
    )
