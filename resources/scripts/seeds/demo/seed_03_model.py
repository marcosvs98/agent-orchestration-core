from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.ai_policy.model import Model

from seeds.demo.ids import MODEL_DEMO_ID


async def seed_model() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Model).where(Model.model_id == MODEL_DEMO_ID)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            model = Model(model_id=MODEL_DEMO_ID, name="gpt-4o-mini")
            session.add(model)
            await session.commit()
