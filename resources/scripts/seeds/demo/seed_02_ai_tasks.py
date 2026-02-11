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
            {
                "id": AI_TASK_INTENT_DETECTION_ID,
                "name": "IntentDetection",
                "allow_rag_tenant": False,
                "allow_user_memory": True,
                "allow_session_context": True,
                "allow_memory_write": False,
            },
            {
                "id": AI_TASK_SLOT_FILLING_ID,
                "name": "SlotFilling",
                "allow_rag_tenant": False,
                "allow_user_memory": True,
                "allow_session_context": True,
                "allow_memory_write": False,
            },
            {
                "id": AI_TASK_RESPONSE_FORMATTING_ID,
                "name": "ResponseFormatting",
                "allow_rag_tenant": True,
                "allow_user_memory": True,
                "allow_session_context": True,
                "allow_memory_write": False,
            },
            {
                "id": AI_TASK_CLARIFICATION_ID,
                "name": "Clarification",
                "allow_rag_tenant": False,
                "allow_user_memory": False,
                "allow_session_context": True,
                "allow_memory_write": False,
            },
        ]

        for task in tasks:
            task_id = task["id"]
            task_name = task["name"]
            result = await session.execute(
                select(AITask).where(
                    (AITask.ai_task_id == task_id) | (AITask.name == task_name)
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                ai_task = AITask(
                    ai_task_id=task_id,
                    name=task_name,
                    allow_rag_tenant=task["allow_rag_tenant"],
                    allow_user_memory=task["allow_user_memory"],
                    allow_session_context=task["allow_session_context"],
                    allow_memory_write=task["allow_memory_write"],
                )
                session.add(ai_task)
            else:
                if existing.ai_task_id != task_id:
                    existing.ai_task_id = task_id
                existing.allow_rag_tenant = task["allow_rag_tenant"]
                existing.allow_user_memory = task["allow_user_memory"]
                existing.allow_session_context = task["allow_session_context"]
                existing.allow_memory_write = task["allow_memory_write"]
                session.add(existing)

        await session.commit()
