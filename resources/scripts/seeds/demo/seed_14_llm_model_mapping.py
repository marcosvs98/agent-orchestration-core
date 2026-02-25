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
    LLM_MODEL_MAPPING_GPT4O_ID,
    LLM_MODEL_MAPPING_GPT4O_LITE_ID,
    LLM_MODEL_MAPPING_GPT4_ID,
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
)


async def seed_llm_model_mapping() -> None:
    async with get_db() as session:
        mappings = [
            (LLM_MODEL_MAPPING_GPT4_ID, "gpt-4o-mini", "gpt-4o-mini"),
            (LLM_MODEL_MAPPING_GPT4O_ID, "gpt-4o", "gpt-4o"),
            (LLM_MODEL_MAPPING_GPT4O_LITE_ID, "gpt-4.1-mini", "gpt-4.1-mini"),
        ]

        for mapping_id, model_alias, provider_model in mappings:
            result = await session.execute(
                select(LLMModelMapping).where(
                    LLMModelMapping.llm_model_mapping_id == mapping_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    LLMModelMapping(
                        llm_model_mapping_id=mapping_id,
                        tenant_id=TENANT_DEMO_ID,
                        provider="OPENAI",
                        model_alias=model_alias,
                        provider_model=provider_model,
                        status="ACTIVE",
                        created_by=PRINCIPAL_SYSTEM,
                    )
                )
            else:
                existing.tenant_id = TENANT_DEMO_ID
                existing.provider = "OPENAI"
                existing.model_alias = model_alias
                existing.provider_model = provider_model
                existing.status = "ACTIVE"
                existing.created_by = PRINCIPAL_SYSTEM
                session.add(existing)

        await session.commit()
