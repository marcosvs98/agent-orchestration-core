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

from seeds.demo.ids import (
    MODEL_CATALOG_GPT41_MINI_ID,
    MODEL_CATALOG_GPT41_NANO_ID,
    MODEL_CATALOG_GPT4O_ID,
    MODEL_CATALOG_O3_MINI_ID,
    MODEL_CATALOG_SLM_QWEN_ID,
    MODEL_DEMO_ID,
)


async def seed_model() -> None:
    catalog = [
        (MODEL_DEMO_ID, "gpt-4o-mini"),
        (MODEL_CATALOG_GPT4O_ID, "gpt-4o"),
        (MODEL_CATALOG_GPT41_MINI_ID, "gpt-4.1-mini"),
        (MODEL_CATALOG_GPT41_NANO_ID, "gpt-4.1-nano"),
        (MODEL_CATALOG_O3_MINI_ID, "o3-mini"),
        (MODEL_CATALOG_SLM_QWEN_ID, "qwen2.5-1.5b-instruct"),
    ]
    async with get_db() as session:
        for model_id, name in catalog:
            by_id = await session.execute(
                select(Model).where(Model.model_id == model_id)
            )
            existing = by_id.scalar_one_or_none()
            if existing is not None:
                existing.name = name
                session.add(existing)
                continue
            taken_name = await session.execute(select(Model).where(Model.name == name))
            if taken_name.scalar_one_or_none() is not None:
                continue
            session.add(Model(model_id=model_id, name=name))
        await session.commit()
