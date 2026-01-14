from uuid import UUID

from domain.governance.ports.access_policy_service import AccessPolicyServicePort
from domain.governance.repositories.access_policy_repository import AccessPolicyRepository
from exceptions.service_exceptions import AuthorizationDeniedException


class AccessPolicyService(AccessPolicyServicePort):
    def __init__(self, repository: AccessPolicyRepository) -> None:
        self.repository = repository

    async def authorize(
        self,
        *,
        tenant_id: UUID,
        principal_type: str,
        principal_id: str,
        scopes: set[str],
        action: str,
    ) -> None:
        policy = await self.repository.get_default_policy_for_tenant(tenant_id)
        if policy is None:
            raise AuthorizationDeniedException(message="access_policy_not_configured")
        policy_version = await self.repository.get_published_policy_version(policy.access_policy_id)
        if policy_version is None:
            raise AuthorizationDeniedException(message="access_policy_version_not_published")

        rules: dict = policy_version.rules or {}
        allowed: set[str] = {str(s) for s in (rules.get("allow") or [])}
        if action not in allowed:
            raise AuthorizationDeniedException(message="action_not_allowed")

        if action not in scopes:
            raise AuthorizationDeniedException(message="missing_required_scope")
