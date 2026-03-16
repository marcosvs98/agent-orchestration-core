from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.flow.node import Node

from seeds.demo.ids import (
    AI_TASK_CLARIFICATION_ID,
    AI_TASK_INTENT_DETECTION_ID,
    AI_TASK_RESPONSE_FORMATTING_ID,
    AI_TASK_SLOT_FILLING_ID,
    FLOW_VERSION_V1_ID,
    NODE_CLARIFICATION_ID,
    NODE_CLARIFICATION_INTENT_ID,
    NODE_FALLBACK_SLA_ID,
    NODE_INPUT_MODERATION_ID,
    NODE_INTENT_ID,
    NODE_PRE_EXEC_VALIDATION_ID,
    NODE_RESPONSE_ID,
    NODE_SLOT_ID,
    NODE_TOOL_ERROR_HANDLER_ID,
    NODE_TOOL_EXEC_ID,
    NODE_TOOL_SELECTION_ID,
    NODE_USER_CONTEXT_ENRICHMENT_ID,
)


async def seed_nodes() -> None:
    async with get_db() as session:
        nodes = [
            (NODE_INPUT_MODERATION_ID, None, "InputModeration"),
            (NODE_USER_CONTEXT_ENRICHMENT_ID, None, "UserContextEnrichment"),
            (NODE_INTENT_ID, AI_TASK_INTENT_DETECTION_ID, "IntentDetection"),
            (NODE_CLARIFICATION_INTENT_ID, AI_TASK_CLARIFICATION_ID, "ClarificationIntent"),
            (NODE_TOOL_SELECTION_ID, None, "ToolSelection"),
            (NODE_SLOT_ID, AI_TASK_SLOT_FILLING_ID, "SlotFilling"),
            (NODE_PRE_EXEC_VALIDATION_ID, None, "PreExecutionValidation"),
            (NODE_TOOL_EXEC_ID, None, "ToolExecution"),
            (NODE_TOOL_ERROR_HANDLER_ID, None, "ToolErrorHandler"),
            (NODE_RESPONSE_ID, AI_TASK_RESPONSE_FORMATTING_ID, "ResponseFormatting"),
            (NODE_CLARIFICATION_ID, AI_TASK_CLARIFICATION_ID, "ClarificationSlot"),
            (NODE_FALLBACK_SLA_ID, None, "FallbackSLA"),
        ]

        for node_id, ai_task_id, node_name in nodes:
            result = await session.execute(
                select(Node).where(Node.node_id == node_id)
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                node = Node(
                    node_id=node_id,
                    flow_version_id=FLOW_VERSION_V1_ID,
                    ai_task_id=ai_task_id,
                )
                session.add(node)

        await session.commit()
