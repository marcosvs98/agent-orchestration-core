from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.tenant import Tenant

from seeds.demo.ids import TENANT_DEMO_ID


async def seed_tenant() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == TENANT_DEMO_ID)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            tenant = Tenant(
                tenant_id=TENANT_DEMO_ID,
                name="Assistente de Bolso",
                description="Agente financeiro conversacional via WhatsApp: controle financeiro pessoal com integração bancária (Open Finance), categorização de gastos, relatórios, metas financeiras e compromissos.",
                is_active=True,
                timezone="America/Sao_Paulo",
                currency="BRL",
                language="pt-BR",
            )
            session.add(tenant)
            await session.commit()
