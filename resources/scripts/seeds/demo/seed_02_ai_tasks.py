from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.ai_policy.ai_task import AITask

from seeds.demo.ids import (
    AI_TASK_INTENT_DETECTION_ID,
    AI_TASK_RESPONSE_FORMATTING_ID,
    AI_TASK_SLOT_FILLING_ID,
    AI_TASK_CLARIFICATION_ID,
)


async def seed_ai_tasks() -> None:
    async with get_db() as session:
        tasks = [
            (AI_TASK_INTENT_DETECTION_ID, "IntentDetection"),
            (AI_TASK_SLOT_FILLING_ID, "SlotFilling"),
            (AI_TASK_RESPONSE_FORMATTING_ID, "ResponseFormatting"),
            (AI_TASK_CLARIFICATION_ID, "Clarification"),
        ]

        for task_id, task_name in tasks:
            result = await session.execute(
                select(AITask).where(
                    (AITask.ai_task_id == task_id) | (AITask.name == task_name)
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                ai_task = AITask(ai_task_id=task_id, name=task_name)
                session.add(ai_task)
            elif existing.ai_task_id != task_id:
                existing.ai_task_id = task_id
                session.add(existing)

        await session.commit()
