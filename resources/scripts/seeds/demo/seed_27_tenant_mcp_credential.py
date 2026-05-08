from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from infra.database import get_db
from infra.database.models.governance.tenant_mcp_credential import TenantMcpCredential

from seeds.demo.ids import (
    MCP_SEED_DEMO_API_KEY,
    MCP_SERVER_DEMO_ID,
    TENANT_DEMO_ID,
    TENANT_MCP_CREDENTIAL_DEMO_ID,
)


async def seed_tenant_mcp_credential() -> None:
    outbound_key = os.getenv("DEMO_OUTBOUND_API_KEY", "demo-outbound-api-key-v1").strip()
    async with get_db() as session:
        result = await session.execute(
            select(TenantMcpCredential).where(
                TenantMcpCredential.tenant_mcp_credential_id
                == TENANT_MCP_CREDENTIAL_DEMO_ID
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                TenantMcpCredential(
                    tenant_mcp_credential_id=TENANT_MCP_CREDENTIAL_DEMO_ID,
                    tenant_id=TENANT_DEMO_ID,
                    mcp_server_id=MCP_SERVER_DEMO_ID,
                    mcp_access_key=MCP_SEED_DEMO_API_KEY,
                    outbound_api_key=outbound_key,
                )
            )
        else:
            existing.mcp_access_key = MCP_SEED_DEMO_API_KEY
            existing.outbound_api_key = outbound_key
            existing.revoked_at = None
            session.add(existing)
        await session.commit()
