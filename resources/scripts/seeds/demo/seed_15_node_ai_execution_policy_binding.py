from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.ai_policy.node_ai_execution_policy_binding import (
    NodeAIExecutionPolicyBinding,
)

from seeds.demo.ids import (
    NODE_AI_EXECUTION_POLICY_BINDING_CLARIFICATION_INTENT_ID,
    NODE_AI_EXECUTION_POLICY_BINDING_INTENT_ID,
    NODE_AI_EXECUTION_POLICY_BINDING_RESPONSE_ID,
    NODE_AI_EXECUTION_POLICY_BINDING_SLOT_ID,
    NODE_AI_EXECUTION_POLICY_BINDING_CLARIFICATION_ID,
    NODE_CLARIFICATION_INTENT_ID,
    NODE_INTENT_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_CLARIFICATION_ID,
    POLICY_VERSION_V1_ID,
)


async def seed_node_ai_execution_policy_binding() -> None:
    async with get_db() as session:
        bindings = [
            (
                NODE_AI_EXECUTION_POLICY_BINDING_INTENT_ID,
                NODE_INTENT_ID,
                POLICY_VERSION_V1_ID,
            ),
            (
                NODE_AI_EXECUTION_POLICY_BINDING_SLOT_ID,
                NODE_SLOT_ID,
                POLICY_VERSION_V1_ID,
            ),
            (
                NODE_AI_EXECUTION_POLICY_BINDING_RESPONSE_ID,
                NODE_RESPONSE_ID,
                POLICY_VERSION_V1_ID,
            ),
            (
                NODE_AI_EXECUTION_POLICY_BINDING_CLARIFICATION_ID,
                NODE_CLARIFICATION_ID,
                POLICY_VERSION_V1_ID,
            ),
            (
                NODE_AI_EXECUTION_POLICY_BINDING_CLARIFICATION_INTENT_ID,
                NODE_CLARIFICATION_INTENT_ID,
                POLICY_VERSION_V1_ID,
            ),
        ]

        for binding_id, node_id, policy_version_id in bindings:
            result = await session.execute(
                select(NodeAIExecutionPolicyBinding).where(
                    NodeAIExecutionPolicyBinding.node_ai_execution_policy_binding_id
                    == binding_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                binding = NodeAIExecutionPolicyBinding(
                    node_ai_execution_policy_binding_id=binding_id,
                    node_id=node_id,
                    ai_execution_policy_version_id=policy_version_id,
                )
                session.add(binding)

        await session.commit()
