import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from domain.governance.services.access_policy_service import AccessPolicyService
from exceptions.service_exceptions import AuthorizationDeniedException


class _FakeTracer:
    @contextlib.contextmanager
    def observe(self, **_):
        yield MagicMock()


def _service(mocker, *, allow: list[str]) -> AccessPolicyService:
    repository = mocker.MagicMock()
    repository.get_default_policy_for_tenant = mocker.AsyncMock(
        return_value=SimpleNamespace(access_policy_id=uuid4(), to_dict=lambda: {})
    )
    repository.get_published_policy_version = mocker.AsyncMock(
        return_value=SimpleNamespace(rules={"allow": allow}, to_dict=lambda: {})
    )
    return AccessPolicyService(repository=repository, tracer=_FakeTracer())


@pytest.mark.asyncio
async def test_access_policy_blocks_missing_scope(mocker):
    """The action is permitted by policy but absent from the caller's token scopes."""

    service = _service(mocker, allow=["execution:run:create"])

    with pytest.raises(AuthorizationDeniedException, match="missing_required_scope"):
        await service.authorize(
            tenant_id=uuid4(),
            principal_type="service",
            principal_id="p",
            scopes={"other:scope"},
            action="execution:run:create",
        )


@pytest.mark.asyncio
async def test_access_policy_blocks_action_the_policy_does_not_allow(mocker):
    """Holding the scope is not enough — the tenant policy must allow the action too."""

    service = _service(mocker, allow=["something:else"])

    with pytest.raises(AuthorizationDeniedException, match="action_not_allowed"):
        await service.authorize(
            tenant_id=uuid4(),
            principal_type="service",
            principal_id="p",
            scopes={"execution:run:create"},
            action="execution:run:create",
        )


@pytest.mark.asyncio
async def test_access_policy_allows_when_policy_and_scope_agree(mocker):
    service = _service(mocker, allow=["execution:run:create"])

    await service.authorize(
        tenant_id=uuid4(),
        principal_type="service",
        principal_id="p",
        scopes={"execution:run:create"},
        action="execution:run:create",
    )


@pytest.mark.asyncio
async def test_access_policy_fails_closed_without_a_configured_policy(mocker):
    repository = mocker.MagicMock()
    repository.get_default_policy_for_tenant = mocker.AsyncMock(return_value=None)
    service = AccessPolicyService(repository=repository, tracer=_FakeTracer())

    with pytest.raises(AuthorizationDeniedException, match="access_policy_not_configured"):
        await service.authorize(
            tenant_id=uuid4(),
            principal_type="service",
            principal_id="p",
            scopes={"execution:run:create"},
            action="execution:run:create",
        )
