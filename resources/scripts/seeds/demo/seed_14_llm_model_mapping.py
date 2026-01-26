from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.llm_model_mapping import LLMModelMapping

from seeds.demo.ids import (
    LLM_MODEL_MAPPING_GPT4_ID,
    LLM_MODEL_MAPPING_FAKE_MODEL_ID,
    TENANT_DEMO_ID,
    PRINCIPAL_SYSTEM,
)


async def seed_llm_model_mapping() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(LLMModelMapping).where(
                LLMModelMapping.llm_model_mapping_id == LLM_MODEL_MAPPING_GPT4_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            model_mapping = LLMModelMapping(
                llm_model_mapping_id=LLM_MODEL_MAPPING_GPT4_ID,
                tenant_id=TENANT_DEMO_ID,
                provider="OPENAI",
                model_alias="gpt-4",
                provider_model="gpt-4o-mini",
                status="ACTIVE",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(model_mapping)

        result = await session.execute(
            select(LLMModelMapping).where(
                LLMModelMapping.llm_model_mapping_id == LLM_MODEL_MAPPING_FAKE_MODEL_ID
            )
        )
        existing_fake = result.scalar_one_or_none()

        if existing_fake is None:
            fake_model_mapping = LLMModelMapping(
                llm_model_mapping_id=LLM_MODEL_MAPPING_FAKE_MODEL_ID,
                tenant_id=TENANT_DEMO_ID,
                provider="OPENAI",
                model_alias="fake-model",
                provider_model="gpt-4o-mini",
                status="ACTIVE",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(fake_model_mapping)

        await session.commit()
