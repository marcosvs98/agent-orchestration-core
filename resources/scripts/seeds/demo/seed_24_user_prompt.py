from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.prompts.user_prompt import UserPrompt

from seeds.demo.ids import PRINCIPAL_SYSTEM, TENANT_DEMO_ID, USER_PROMPT_DEMO_ID


async def seed_user_prompt() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(UserPrompt).where(UserPrompt.user_prompt_id == USER_PROMPT_DEMO_ID)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            user_prompt = UserPrompt(
                user_prompt_id=USER_PROMPT_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                title="financial_context_default",
                content=(
                    "Prioritize objective financial guidance. "
                    "If user intent is ambiguous, ask one direct clarification question. "
                    "When possible, present concise recommendations with clear next action."
                ),
                version=1,
                is_active=True,
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(user_prompt)
        else:
            existing.tenant_id = TENANT_DEMO_ID
            existing.title = "financial_context_default"
            existing.content = (
                "Prioritize objective financial guidance. "
                "If user intent is ambiguous, ask one direct clarification question. "
                "When possible, present concise recommendations with clear next action."
            )
            existing.version = max(int(existing.version or 1), 1)
            existing.is_active = True
            existing.created_by = PRINCIPAL_SYSTEM
            session.add(existing)

        await session.commit()
