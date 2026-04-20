from __future__ import annotations

import pytest
import sqlalchemy as sa

from infra.database.models.governance.tenant import Tenant
from resources.scripts.validation_seed import TENANT_ID

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_database_is_ready(db_session) -> None:
    result = await db_session.execute(sa.text("SELECT 1"))
    assert int(result.scalar_one()) == 1
    tenant = await db_session.get(Tenant, TENANT_ID)
    assert tenant is not None
