from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.flow.router import Router
from infra.database.models.routing.condition_expression import ConditionExpression
from infra.database.models.routing.routing_rule import RoutingRule

from seeds.demo.ids import (
    CONDITION_EXPRESSION_DEMO_ID,
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    ROUTER_DEMO_ID,
    ROUTING_RULE_DEMO_ID,
)


async def seed_router() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Router).where(Router.router_id == ROUTER_DEMO_ID)
        )
        existing_router = result.scalar_one_or_none()

        if existing_router is None:
            router = Router(router_id=ROUTER_DEMO_ID, node_id=NODE_INTENT_ID)
            session.add(router)
            await session.commit()

        result = await session.execute(
            select(ConditionExpression).where(
                ConditionExpression.condition_expression_id == CONDITION_EXPRESSION_DEMO_ID
            )
        )
        existing_condition = result.scalar_one_or_none()

        if existing_condition is None:
            condition = ConditionExpression(
                condition_expression_id=CONDITION_EXPRESSION_DEMO_ID,
                expression='ctx.get("intent") == "payment"',
            )
            session.add(condition)
            await session.commit()

        result = await session.execute(
            select(RoutingRule).where(
                RoutingRule.routing_rule_id == ROUTING_RULE_DEMO_ID
            )
        )
        existing_rule = result.scalar_one_or_none()

        if existing_rule is None:
            routing_rule = RoutingRule(
                routing_rule_id=ROUTING_RULE_DEMO_ID,
                router_id=ROUTER_DEMO_ID,
                condition_expression_id=CONDITION_EXPRESSION_DEMO_ID,
                from_node_id=NODE_INTENT_ID,
                to_node_id=NODE_SLOT_ID,
            )
            session.add(routing_rule)
            await session.commit()
