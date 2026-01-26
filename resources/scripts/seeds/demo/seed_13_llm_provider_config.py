from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.llm_provider_config import LLMProviderConfig

from seeds.demo.ids import (
    LLM_PROVIDER_CONFIG_OPENAI_ID,
    TENANT_DEMO_ID,
    PRINCIPAL_SYSTEM,
)


async def seed_llm_provider_config() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(LLMProviderConfig).where(
                LLMProviderConfig.llm_provider_config_id == LLM_PROVIDER_CONFIG_OPENAI_ID
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            provider_config = LLMProviderConfig(
                llm_provider_config_id=LLM_PROVIDER_CONFIG_OPENAI_ID,
                tenant_id=TENANT_DEMO_ID,
                provider="OPENAI",
                status="ACTIVE",
                base_url=None,
                credential_secret_ref="env:openai_api_key",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(provider_config)
        else:
            if existing.credential_secret_ref != "env:openai_api_key":
                existing.credential_secret_ref = "env:openai_api_key"
        await session.commit()
