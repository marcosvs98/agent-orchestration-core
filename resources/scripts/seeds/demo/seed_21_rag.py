from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.rag.rag_config import RagConfig
from infra.database.models.rag.vector_store import VectorStore

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    VECTOR_STORE_DEMO_ID,
)


async def seed_rag() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(VectorStore).where(
                VectorStore.vector_store_id == VECTOR_STORE_DEMO_ID
            )
        )
        existing_store = result.scalar_one_or_none()

        if existing_store is None:
            vector_store = VectorStore(
                vector_store_id=VECTOR_STORE_DEMO_ID,
                name="Demo Vector Store",
            )
            session.add(vector_store)
            await session.commit()

        result = await session.execute(
            select(RagConfig).where(RagConfig.rag_config_id == RAG_CONFIG_DEMO_ID)
        )
        existing_config = result.scalar_one_or_none()

        if existing_config is None:
            rag_config = RagConfig(
                rag_config_id=RAG_CONFIG_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                vector_store_id=VECTOR_STORE_DEMO_ID,
                status="DRAFT",
                version_major=1,
                version_minor=0,
                version_patch=0,
                options=None,
            )
            session.add(rag_config)
            await session.commit()
