from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from infra.database import get_db
from infra.database.models.flow.flow import Flow
from infra.database.models.flow.flow_version import FlowVersion

from seeds.demo.ids import (
    FLOW_DEMO_ID,
    FLOW_VERSION_V1_ID,
    PRINCIPAL_SYSTEM,
    TENANT_DEMO_ID,
)


async def seed_flow() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Flow).where(Flow.flow_id == FLOW_DEMO_ID)
        )
        flow = result.scalar_one_or_none()

        if flow is None:
            flow = Flow(
                flow_id=FLOW_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                name="fluxo-uora",
                description="Fluxo conversacional do Uora: intent, extração de parâmetros, execução de ferramentas (registro de despesas/receitas, consultas, metas, lembretes) e resposta ao usuário.",
                created_by=PRINCIPAL_SYSTEM,
            )
            session.add(flow)
            await session.commit()

        result = await session.execute(
            select(FlowVersion).where(
                FlowVersion.flow_version_id == FLOW_VERSION_V1_ID
            )
        )
        flow_version = result.scalar_one_or_none()

        if flow_version is None:
            flow_version = FlowVersion(
                flow_version_id=FLOW_VERSION_V1_ID,
                flow_id=FLOW_DEMO_ID,
                status=VersionStatus.DRAFT.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
            )
            session.add(flow_version)
            await session.commit()
