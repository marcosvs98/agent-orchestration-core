"""GovernancePoliciesService — tenant ownership across every policy family.

The version create/publish/activate paths take a `tenant_id` and must refuse to touch a policy
owned by another tenant, answering not-found rather than forbidden so a foreign UUID is never
confirmed. This exercises all five families plus the runtime policy, which have identical shapes
and therefore identical ways to go wrong.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.common.schemas.change import ChangeRequest
from domain.governance.schemas.memory_policy import MemoryPolicyDefinition
from domain.governance.schemas.policy_admin import (
    AccessPolicyVersionCreate,
    BillingPolicyVersionCreate,
    MemoryPolicyVersionCreate,
    RagPolicyVersionCreate,
    RateLimitPolicyVersionCreate,
)
from domain.governance.schemas.rag_policy import RagPolicyDefinition
from domain.governance.services.governance_policies_service import (
    GovernancePoliciesService,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)

OWNER = uuid4()
INTRUDER = uuid4()
CHANGE = ChangeRequest(change_type="UPDATE", justification="because")


def _repository(*, policy_tenant_id, version_fields: dict) -> MagicMock:
    repository = MagicMock()
    repository.get_policy = AsyncMock(
        return_value=SimpleNamespace(tenant_id=policy_tenant_id, name="p")
    )
    repository.get_version = AsyncMock(return_value=SimpleNamespace(**version_fields))
    repository.create_version = AsyncMock(return_value=SimpleNamespace(**version_fields))
    repository.set_version_status = AsyncMock()
    repository.set_active_version = AsyncMock()
    return repository


def _version_fields(parent_key: str, parent_id, **extra) -> dict:
    base = {
        parent_key: parent_id,
        "status": "PUBLISHED",
        "version_major": 1,
        "version_minor": 0,
        "version_patch": 0,
    }
    base.update(extra)
    return base


def _service(**repositories) -> GovernancePoliciesService:
    defaults = {
        "runtime_repository": MagicMock(),
        "access_repository": MagicMock(),
        "rate_limit_repository": MagicMock(),
        "billing_repository": MagicMock(),
        "memory_repository": MagicMock(),
        "rag_repository": MagicMock(),
    }
    defaults.update(repositories)
    return GovernancePoliciesService(**defaults)


class TestAccessPolicyVersions:
    def _service(self, policy_tenant_id):
        repository = _repository(
            policy_tenant_id=policy_tenant_id,
            version_fields=_version_fields(
                "access_policy_id",
                uuid4(),
                access_policy_version_id=uuid4(),
                rules={},
            ),
        )
        return _service(access_repository=repository), repository

    @pytest.mark.asyncio
    async def test_create_version_for_own_policy(self):
        service, repository = self._service(OWNER)

        await service.create_access_policy_version(
            tenant_id=OWNER,
            access_policy_id=uuid4(),
            payload=AccessPolicyVersionCreate(),
        )

        repository.create_version.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_version_for_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="access_policy_not_found"):
            await service.create_access_policy_version(
                tenant_id=INTRUDER,
                access_policy_id=uuid4(),
                payload=AccessPolicyVersionCreate(),
            )

        repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_version_of_own_policy(self):
        service, repository = self._service(OWNER)

        await service.publish_access_policy_version(
            tenant_id=OWNER, access_policy_version_id=uuid4()
        )

        repository.set_version_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_version_of_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="access_policy_version_not_found"):
            await service.publish_access_policy_version(
                tenant_id=INTRUDER, access_policy_version_id=uuid4()
            )

        repository.set_version_status.assert_not_called()


class TestRateLimitPolicyVersions:
    def _service(self, policy_tenant_id):
        repository = _repository(
            policy_tenant_id=policy_tenant_id,
            version_fields=_version_fields(
                "rate_limit_policy_id",
                uuid4(),
                rate_limit_policy_version_id=uuid4(),
                action="a",
                principal_type="service",
                limit=1,
                window_seconds=60,
            ),
        )
        return _service(rate_limit_repository=repository), repository

    @pytest.mark.asyncio
    async def test_create_version_for_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="rate_limit_policy_not_found"):
            await service.create_rate_limit_policy_version(
                tenant_id=INTRUDER,
                rate_limit_policy_id=uuid4(),
                payload=RateLimitPolicyVersionCreate(
                    action="a", principal_type="service", limit=1, window_seconds=60
                ),
            )

        repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_version_of_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="rate_limit_policy_version_not_found"):
            await service.publish_rate_limit_policy_version(
                tenant_id=INTRUDER, rate_limit_policy_version_id=uuid4()
            )

        repository.set_version_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_version_of_own_policy(self):
        service, repository = self._service(OWNER)

        await service.publish_rate_limit_policy_version(
            tenant_id=OWNER, rate_limit_policy_version_id=uuid4()
        )

        repository.set_version_status.assert_awaited_once()


class TestBillingPolicyVersions:
    def _service(self, policy_tenant_id):
        repository = _repository(
            policy_tenant_id=policy_tenant_id,
            version_fields=_version_fields(
                "billing_policy_id",
                uuid4(),
                billing_policy_version_id=uuid4(),
                rules={},
            ),
        )
        return _service(billing_repository=repository), repository

    @pytest.mark.asyncio
    async def test_create_version_for_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="billing_policy_not_found"):
            await service.create_billing_policy_version(
                tenant_id=INTRUDER,
                billing_policy_id=uuid4(),
                payload=BillingPolicyVersionCreate(),
            )

        repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_foreign_version_never_repoints_the_active_pointer(self):
        """A tenant must not be able to point its own active version at a foreign one."""

        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="billing_policy_version_not_found"):
            await service.activate_billing_policy_version(
                tenant_id=INTRUDER,
                billing_policy_version_id=uuid4(),
                principal_id="p",
                change_request=CHANGE,
            )

        repository.set_active_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_requires_a_justification(self):
        service, repository = self._service(OWNER)

        with pytest.raises(DomainValidationException, match="justification_required"):
            await service.activate_billing_policy_version(
                tenant_id=OWNER,
                billing_policy_version_id=uuid4(),
                principal_id="p",
                change_request=ChangeRequest(change_type="UPDATE", justification="   "),
            )

        repository.set_active_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_own_version(self):
        service, repository = self._service(OWNER)

        await service.activate_billing_policy_version(
            tenant_id=OWNER,
            billing_policy_version_id=uuid4(),
            principal_id="p",
            change_request=CHANGE,
        )

        repository.set_active_version.assert_awaited_once()


class TestMemoryPolicyVersions:
    def _service(self, policy_tenant_id):
        repository = _repository(
            policy_tenant_id=policy_tenant_id,
            version_fields=_version_fields(
                "memory_policy_id",
                uuid4(),
                memory_policy_version_id=uuid4(),
                retention_ttl_seconds=60,
                consent_definition={},
                allowed_sources=[],
                allowed_schemas=[],
            ),
        )
        return _service(memory_repository=repository), repository

    @pytest.mark.asyncio
    async def test_create_version_for_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="memory_policy_not_found"):
            await service.create_memory_policy_version(
                tenant_id=INTRUDER,
                memory_policy_id=uuid4(),
                payload=MemoryPolicyVersionCreate(
                    definition=MemoryPolicyDefinition(retention_ttl_seconds=60)
                ),
            )

        repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_foreign_version_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="memory_policy_version_not_found"):
            await service.activate_memory_policy_version(
                tenant_id=INTRUDER,
                memory_policy_version_id=uuid4(),
                principal_id="p",
                change_request=CHANGE,
            )

        repository.set_active_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_own_version(self):
        service, repository = self._service(OWNER)

        await service.publish_memory_policy_version(
            tenant_id=OWNER, memory_policy_version_id=uuid4()
        )

        repository.set_version_status.assert_awaited_once()


class TestRagPolicyVersions:
    def _service(self, policy_tenant_id):
        repository = _repository(
            policy_tenant_id=policy_tenant_id,
            version_fields=_version_fields(
                "rag_policy_id",
                uuid4(),
                rag_policy_version_id=uuid4(),
                policy_definition={},
            ),
        )
        return _service(rag_repository=repository), repository

    @pytest.mark.asyncio
    async def test_create_version_for_foreign_policy_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="rag_policy_not_found"):
            await service.create_rag_policy_version(
                tenant_id=INTRUDER,
                rag_policy_id=uuid4(),
                payload=RagPolicyVersionCreate(definition=RagPolicyDefinition()),
            )

        repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_foreign_version_is_not_found(self):
        service, repository = self._service(OWNER)

        with pytest.raises(NotFoundServiceException, match="rag_policy_version_not_found"):
            await service.publish_rag_policy_version(
                tenant_id=INTRUDER, rag_policy_version_id=uuid4()
            )

        repository.set_version_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_own_version(self):
        service, repository = self._service(OWNER)

        await service.activate_rag_policy_version(
            tenant_id=OWNER,
            rag_policy_version_id=uuid4(),
            principal_id="p",
            change_request=CHANGE,
        )

        repository.set_active_version.assert_awaited_once()


class TestRuntimePolicyActivation:
    @pytest.mark.asyncio
    async def test_activate_foreign_runtime_policy_is_not_found(self):
        repository = MagicMock()
        repository.get_policy = AsyncMock(
            return_value=SimpleNamespace(tenant_id=OWNER, policy_definition={})
        )
        repository.activate_policy = AsyncMock()
        service = _service(runtime_repository=repository)

        with pytest.raises(NotFoundServiceException, match="runtime_policy_not_found"):
            await service.activate_runtime_policy(
                tenant_id=INTRUDER,
                runtime_policy_id=uuid4(),
                principal_id="p",
                change_request=CHANGE,
            )

        repository.activate_policy.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_requires_a_justification(self):
        repository = MagicMock()
        repository.get_policy = AsyncMock(
            return_value=SimpleNamespace(tenant_id=OWNER, policy_definition={})
        )
        repository.activate_policy = AsyncMock()
        service = _service(runtime_repository=repository)

        with pytest.raises(DomainValidationException, match="justification_required"):
            await service.activate_runtime_policy(
                tenant_id=OWNER,
                runtime_policy_id=uuid4(),
                principal_id="p",
                change_request=ChangeRequest(change_type="UPDATE", justification=""),
            )

        repository.activate_policy.assert_not_called()
