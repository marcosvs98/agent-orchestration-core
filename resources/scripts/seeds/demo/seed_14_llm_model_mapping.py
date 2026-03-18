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
from infra.database.models.governance.llm_model_mapping import LLMModelMapping

from seeds.demo.ids import (
    LLM_MODEL_MAPPING_GPT4_ID,
    LLM_MODEL_MAPPING_GPT4O_ID,
    LLM_MODEL_MAPPING_GPT4O_LITE_ID,
    LLM_MODEL_MAPPING_GPT41_NANO_ID,
    LLM_MODEL_MAPPING_O3_MINI_ID,
    LLM_MODEL_MAPPING_SLM_LOCAL_ID,
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
)


async def seed_llm_model_mapping() -> None:
    mappings = [
        (LLM_MODEL_MAPPING_GPT4_ID, "OPENAI", "gpt-4o-mini", "gpt-4o-mini"),
        (LLM_MODEL_MAPPING_GPT4O_ID, "OPENAI", "gpt-4o", "gpt-4o"),
        (
            LLM_MODEL_MAPPING_GPT4O_LITE_ID,
            "OPENAI",
            "gpt-4.1-mini",
            "gpt-4.1-mini",
        ),
        (
            LLM_MODEL_MAPPING_GPT41_NANO_ID,
            "OPENAI",
            "gpt-4.1-nano",
            "gpt-4.1-nano",
        ),
        (
            LLM_MODEL_MAPPING_O3_MINI_ID,
            "OPENAI",
            "o3-mini",
            "o3-mini",
        ),
        (
            LLM_MODEL_MAPPING_SLM_LOCAL_ID,
            "SLM_LOCAL",
            "qwen2.5-1.5b-instruct",
            "qwen2.5-1.5b-instruct-q4_k_m",
        ),
    ]

    async with get_db() as session:
        for mapping_id, provider, model_alias, provider_model in mappings:
            mid = (
                await session.execute(
                    select(Model.model_id).where(Model.name == model_alias)
                )
            ).scalar_one_or_none()
            if mid is None:
                raise RuntimeError(
                    f"model catalog missing name={model_alias!r}; run Model seed before "
                    "llm_model_mapping"
                )
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
                        model_id=mid,
                        provider=provider,
                        model_alias=model_alias,
                        provider_model=provider_model,
                        status="ACTIVE",
                        created_by=PRINCIPAL_SYSTEM,
                    )
                )
            else:
                existing.tenant_id = TENANT_DEMO_ID
                existing.model_id = mid
                existing.provider = provider
                existing.model_alias = model_alias
                existing.provider_model = provider_model
                existing.status = "ACTIVE"
                existing.created_by = PRINCIPAL_SYSTEM
                session.add(existing)

        await session.commit()
