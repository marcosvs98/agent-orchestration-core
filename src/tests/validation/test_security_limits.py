from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.governance.services.access_policy_service import AccessPolicyService
from exceptions.service_exceptions import AuthorizationDeniedException


@pytest.mark.asyncio
async def test_access_policy_blocks_missing_scope(mocker):
    tenant_id = uuid4()
    repo = mocker.MagicMock()
    repo.get_default_policy_for_tenant = mocker.AsyncMock(
        return_value=SimpleNamespace(access_policy_id=uuid4())
    )
    repo.get_published_policy_version = mocker.AsyncMock(
        return_value=SimpleNamespace(rules={"allow": ["execution:run:create"]})
    )
    service = AccessPolicyService(repository=repo)

    with pytest.raises(AuthorizationDeniedException, match="missing_required_scope"):
        await service.authorize(
            tenant_id=tenant_id,
            principal_type="service",
            principal_id="p",
            scopes={"other:scope"},
            action="execution:run:create",
        )
