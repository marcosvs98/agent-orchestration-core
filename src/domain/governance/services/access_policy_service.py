from uuid import UUID

from domain.governance.ports.access_policy_service import AccessPolicyServicePort
from domain.governance.repositories.access_policy_repository import (
    AccessPolicyRepository,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from exceptions.service_exceptions import AuthorizationDeniedException


class AccessPolicyService(AccessPolicyServicePort):
    def __init__(
        self, repository: AccessPolicyRepository, tracer: RuntimeTracerPort
    ) -> None:
        self.repository = repository
        self.tracer = tracer

    async def authorize(
        self,
        *,
        tenant_id: UUID,
        principal_type: str,
        principal_id: str,
        scopes: set[str],
        action: str,
    ) -> None:
        with self.tracer.observe(
            as_type="guardrail",
            name="governance.access_policy.authorize",
            input={
                "tenant_id": str(tenant_id),
                "action": action,
                "principal_type": principal_type,
            },
            metadata={"guardrail_type": "access_policy"},
        ):
            with self.tracer.observe(
                as_type="retriever",
                name="governance.access_policy.get_default_policy",
                input={"tenant_id": str(tenant_id)},
            ) as policy_handle:
                policy = await self.repository.get_default_policy_for_tenant(tenant_id)
                if policy_handle:
                    policy_handle.success(output={"found": policy is not None})
        if policy is None:
            with self.tracer.observe(
                as_type="event",
                name="governance.access_policy.missing",
                input={"tenant_id": str(tenant_id), "action": action},
            ):
                pass
            raise AuthorizationDeniedException(message="access_policy_not_configured")

        with self.tracer.observe(
            as_type="retriever",
            name="governance.access_policy.get_policy_version",
            input={"policy_id": str(policy.access_policy_id)},
        ) as version_handle:
            policy_version = await self.repository.get_published_policy_version(
                policy.access_policy_id
            )
            if version_handle:
                version_handle.success(output={"found": policy_version is not None})
        if policy_version is None:
            with self.tracer.observe(
                as_type="event",
                name="governance.access_policy.unpublished",
                input={"policy_id": str(policy.access_policy_id)},
            ):
                pass
            raise AuthorizationDeniedException(
                message="access_policy_version_not_published"
            )

        rules: dict = policy_version.rules or {}
        allowed: set[str] = {str(s) for s in (rules.get("allow") or [])}
        if action not in allowed:
            with self.tracer.observe(
                as_type="event",
                name="governance.access_policy.denied",
                input={"tenant_id": str(tenant_id), "action": action},
            ):
                pass
            raise AuthorizationDeniedException(message="action_not_allowed")

        if action not in scopes:
            with self.tracer.observe(
                as_type="event",
                name="governance.access_policy.missing_scope",
                input={"tenant_id": str(tenant_id), "action": action},
            ):
                pass
            raise AuthorizationDeniedException(message="missing_required_scope")
