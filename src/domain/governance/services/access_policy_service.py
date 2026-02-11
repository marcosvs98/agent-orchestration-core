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
                "principal_id": principal_id,
            },
            metadata={"guardrail_type": "access_policy"},
        ) as guardrail_handle:
            policy = await self.repository.get_default_policy_for_tenant(tenant_id)

            if policy is None:
                if guardrail_handle:
                    guardrail_handle.error(
                        error_type="AuthorizationDenied",
                        error_message="access_policy_not_configured",
                        output={
                            "reason": "access_policy_not_configured",
                            "tenant_id": str(tenant_id),
                            "action": action,
                        },
                    )
                raise AuthorizationDeniedException(
                    message="access_policy_not_configured"
                )

            policy_version = await self.repository.get_published_policy_version(
                policy.access_policy_id
            )
            if policy_version is None:
                if guardrail_handle:
                    guardrail_handle.error(
                        error_type="AuthorizationDenied",
                        error_message="access_policy_version_not_published",
                        output={
                            "reason": "access_policy_version_not_published",
                            "policy_id": str(policy.access_policy_id),
                        },
                    )
                raise AuthorizationDeniedException(
                    message="access_policy_version_not_published"
                )

            rules: dict = policy_version.rules or {}
            allowed: set[str] = {str(s) for s in (rules.get("allow") or [])}
            if action not in allowed:
                if guardrail_handle:
                    guardrail_handle.error(
                        error_type="AuthorizationDenied",
                        error_message="action_not_allowed",
                        output={
                            "reason": "action_not_allowed",
                            "tenant_id": str(tenant_id),
                            "action": action,
                        },
                    )
                raise AuthorizationDeniedException(message="action_not_allowed")

            if action not in scopes:
                if guardrail_handle:
                    guardrail_handle.error(
                        error_type="AuthorizationDenied",
                        error_message="missing_required_scope",
                        output={
                            "reason": "missing_required_scope",
                            "tenant_id": str(tenant_id),
                            "action": action,
                        },
                    )
                raise AuthorizationDeniedException(message="missing_required_scope")

            if guardrail_handle:
                guardrail_handle.success(
                    output={
                        "policy": policy.to_dict(),
                        "policy_version": policy_version.to_dict(),
                        "authorized": True,
                        "action": action,
                        "tenant_id": str(tenant_id),
                        "principal_type": principal_type,
                        "principal_id": principal_id,
                    }
                )
