from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from domain.human_sla.schemas.human_sla_policy import (
    HumanSLAEscalationRule,
    HumanSLAPolicy,
)
from infra.database import DatabaseConnection
from infra.database.models.escalation.human_sla_escalation_rule import (
    HumanSLAEscalationRule as HumanSLAEscalationRuleORM,
)
from infra.database.models.escalation.human_sla_policy import (
    HumanSLAPolicy as HumanSLAPolicyORM,
)


class HumanSLAPolicyRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def list_by_tenant(self, tenant_id: UUID) -> list[HumanSLAPolicy]:
        async with self.db.get_session() as session:
            stmt = (
                select(HumanSLAPolicyORM)
                .where(HumanSLAPolicyORM.tenant_id == tenant_id)
                .order_by(HumanSLAPolicyORM.name)
            )
            result = await session.execute(stmt)
            return [HumanSLAPolicy.model_validate(r) for r in result.scalars().all()]

    async def resolve_policy(
        self, tenant_id: UUID, node: str, fallback_reason: str
    ) -> HumanSLAPolicy | None:
        async with self.db.get_session() as session:
            stmt = (
                select(HumanSLAPolicyORM)
                .where(
                    HumanSLAPolicyORM.tenant_id == tenant_id,
                    HumanSLAPolicyORM.node == node,
                    HumanSLAPolicyORM.fallback_reason == fallback_reason,
                    HumanSLAPolicyORM.active.is_(True),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return HumanSLAPolicy.model_validate(row)

    async def get_policy_with_rules(self, human_sla_policy_id: UUID) -> HumanSLAPolicy | None:
        async with self.db.get_session() as session:
            stmt = select(HumanSLAPolicyORM).where(
                HumanSLAPolicyORM.human_sla_policy_id == human_sla_policy_id
            )
            result = await session.execute(stmt)
            policy_row = result.scalar_one_or_none()
            if policy_row is None:
                return None
            rules_stmt = (
                select(HumanSLAEscalationRuleORM)
                .where(HumanSLAEscalationRuleORM.human_sla_policy_id == human_sla_policy_id)
                .order_by(HumanSLAEscalationRuleORM.level)
            )
            rules_result = await session.execute(rules_stmt)
            rules = [HumanSLAEscalationRule.model_validate(r) for r in rules_result.scalars().all()]
            return HumanSLAPolicy.model_validate(policy_row).model_copy(
                update={"escalation_rules": rules}
            )
