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
    AI_TASK_INTENT_DETECTION_ID,
    AI_TASK_RESPONSE_FORMATTING_ID,
    AI_TASK_SLOT_FILLING_ID,
    FLOW_VERSION_V1_ID,
    NODE_INTENT_ID,
    NODE_SLOT_ID,
    NODE_TOOL_EXEC_ID,
    NODE_RESPONSE_ID,
)


async def seed_nodes() -> None:
    async with get_db() as session:
        nodes = [
            (NODE_INTENT_ID, AI_TASK_INTENT_DETECTION_ID, "IntentDetection"),
            (NODE_SLOT_ID, AI_TASK_SLOT_FILLING_ID, "SlotFilling"),
            (NODE_TOOL_EXEC_ID, None, "ToolExecution"),
            (NODE_RESPONSE_ID, AI_TASK_RESPONSE_FORMATTING_ID, "ResponseFormatting"),
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
