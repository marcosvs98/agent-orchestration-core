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
    MODEL_CATALOG_EMBEDDING_INDEXING_ID,
    MODEL_CATALOG_EMBEDDING_RETRIEVAL_ID,
    MODEL_CATALOG_GPT41_MINI_ID,
    MODEL_CATALOG_GPT41_NANO_ID,
    MODEL_CATALOG_GPT4O_ID,
    MODEL_CATALOG_O3_MINI_ID,
    MODEL_CATALOG_SLM_QWEN_ID,
    MODEL_DEMO_ID,
)


async def seed_model() -> None:
    catalog = [
        {
            "model_id": MODEL_DEMO_ID,
            "name": "gpt-4o-mini",
            "provider": "openai",
            "type": "LLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_GPT4O_ID,
            "name": "gpt-4o",
            "provider": "openai",
            "type": "LLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_GPT41_MINI_ID,
            "name": "gpt-4.1-mini",
            "provider": "openai",
            "type": "LLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_GPT41_NANO_ID,
            "name": "gpt-4.1-nano",
            "provider": "openai",
            "type": "LLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_O3_MINI_ID,
            "name": "o3-mini",
            "provider": "openai",
            "type": "LLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_SLM_QWEN_ID,
            "name": "qwen2.5-1.5b-instruct",
            "provider": "local",
            "type": "SLM",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_EMBEDDING_RETRIEVAL_ID,
            "name": "text-embedding-3-small",
            "provider": "openai",
            "type": "EMBEDDING",
            "is_active": True,
        },
        {
            "model_id": MODEL_CATALOG_EMBEDDING_INDEXING_ID,
            "name": "text-embedding-3-large",
            "provider": "openai",
            "type": "EMBEDDING",
            "is_active": True,
        },
    ]
    async with get_db() as session:
        for item in catalog:
            model_id = item["model_id"]
            name = item["name"]
            provider = item["provider"]
            model_type = item["type"]
            is_active = item["is_active"]
            by_id = await session.execute(
                select(Model).where(Model.model_id == model_id)
            )
            existing = by_id.scalar_one_or_none()
            if existing is not None:
                existing.name = name
                existing.provider = provider
                existing.type = model_type
                existing.is_active = is_active
                session.add(existing)
                continue
            taken_name = await session.execute(select(Model).where(Model.name == name))
            existing_by_name = taken_name.scalar_one_or_none()
            if existing_by_name is not None:
                existing_by_name.provider = provider
                existing_by_name.type = model_type
                existing_by_name.is_active = is_active
                session.add(existing_by_name)
                continue
            session.add(
                Model(
                    model_id=model_id,
                    name=name,
                    provider=provider,
                    type=model_type,
                    is_active=is_active,
                )
            )
        await session.commit()
