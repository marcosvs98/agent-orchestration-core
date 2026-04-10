from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.tenant import Tenant
from infra.database.models.governance.tenant_inbound_service_key import (
    TenantInboundServiceKey,
)

from seeds.demo.ids import TENANT_DEMO_ID, TENANT_INBOUND_SERVICE_KEY_DEMO_ID


async def seed_tenant() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == TENANT_DEMO_ID)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            tenant = Tenant(
                tenant_id=TENANT_DEMO_ID,
                name="Uora",
                description="Agente financeiro conversacional via WhatsApp: controle financeiro pessoal com integração bancária (Open Finance), categorização de gastos, relatórios, metas financeiras e compromissos.",
                is_active=True,
                timezone="America/Sao_Paulo",
                currency="BRL",
                language="pt-BR",
            )
            session.add(tenant)

        # Alembic migration may skip this row (tenant did not exist yet). App-platform
        # calls /auth/tenant-token with X-Inbound-Service-Key == AOC_API_KEY.
        plain = os.getenv(
            "UORA_DEMO_INBOUND_SERVICE_KEY",
            "aoc-dev-inbound-service-key-tenant-100-v1",
        ).strip()
        digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        key_result = await session.execute(
            select(TenantInboundServiceKey).where(
                TenantInboundServiceKey.inbound_service_key_id
                == TENANT_INBOUND_SERVICE_KEY_DEMO_ID
            )
        )
        existing_key = key_result.scalar_one_or_none()
        if existing_key is None:
            session.add(
                TenantInboundServiceKey(
                    inbound_service_key_id=TENANT_INBOUND_SERVICE_KEY_DEMO_ID,
                    tenant_id=TENANT_DEMO_ID,
                    key_hash=digest,
                )
            )
        else:
            existing_key.key_hash = digest
            existing_key.revoked_at = None
            session.add(existing_key)

        await session.commit()
