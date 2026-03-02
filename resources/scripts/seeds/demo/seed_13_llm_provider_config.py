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
    LLM_PROVIDER_CONFIG_SLM_LOCAL_ID,
    TENANT_DEMO_ID,
    PRINCIPAL_SYSTEM,
)


async def seed_llm_provider_config() -> None:
    async with get_db() as session:
        rows = [
            (
                LLM_PROVIDER_CONFIG_OPENAI_ID,
                "OPENAI",
                None,
                "env:openai_api_key",
            ),
            (
                LLM_PROVIDER_CONFIG_SLM_LOCAL_ID,
                "SLM_LOCAL",
                None,
                '{"n_ctx": 2048, "n_threads": 4, "n_gpu_layers": 0, "n_batch": 64}',
            ),
        ]

        for config_id, provider, base_url, credential_secret_ref in rows:
            result = await session.execute(
                select(LLMProviderConfig).where(
                    LLMProviderConfig.llm_provider_config_id == config_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                session.add(
                    LLMProviderConfig(
                        llm_provider_config_id=config_id,
                        tenant_id=TENANT_DEMO_ID,
                        provider=provider,
                        status="ACTIVE",
                        base_url=base_url,
                        credential_secret_ref=credential_secret_ref,
                        created_by=PRINCIPAL_SYSTEM,
                    )
                )
            else:
                existing.tenant_id = TENANT_DEMO_ID
                existing.provider = provider
                existing.status = "ACTIVE"
                existing.base_url = base_url
                existing.credential_secret_ref = credential_secret_ref
                existing.created_by = PRINCIPAL_SYSTEM
                session.add(existing)
        await session.commit()
