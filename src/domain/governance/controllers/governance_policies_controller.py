from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from domain.common.schemas.change import ChangeRequest
from domain.governance.schemas.policy_admin import (
    AccessPolicyCreate,
    AccessPolicyResponse,
    AccessPolicyVersionCreate,
    AccessPolicyVersionResponse,
    BillingPolicyCreate,
    BillingPolicyResponse,
    BillingPolicyVersionCreate,
    BillingPolicyVersionResponse,
    MemoryPolicyCreate,
    MemoryPolicyResponse,
    MemoryPolicyVersionCreate,
    MemoryPolicyVersionResponse,
    RagPolicyCreate,
    RagPolicyResponse,
    RagPolicyVersionCreate,
    RagPolicyVersionResponse,
    RateLimitPolicyCreate,
    RateLimitPolicyResponse,
    RateLimitPolicyVersionCreate,
    RateLimitPolicyVersionResponse,
    RuntimePolicyCreate,
    RuntimePolicyResponse,
    RuntimePolicyUpdate,
)
from domain.governance.schemas.scopes import Scope
from domain.governance.services.governance_policies_service import GovernancePoliciesService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext, get_auth_context


class GovernancePoliciesController:
    def __init__(self, service: GovernancePoliciesService) -> None:
        self.service = service
        self.router = APIRouter(
            prefix="/core/v1",
            tags=["governance"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r("/runtime-policies", self.create_runtime_policy, methods=["POST"], response_model=RuntimePolicyResponse)
        r("/runtime-policies", self.list_runtime_policies, methods=["GET"], response_model=list[RuntimePolicyResponse])
        r("/runtime-policies/{runtime_policy_id}", self.get_runtime_policy, methods=["GET"], response_model=RuntimePolicyResponse)
        r("/runtime-policies/{runtime_policy_id}", self.update_runtime_policy, methods=["PATCH"], response_model=RuntimePolicyResponse)
        r("/runtime-policies/{runtime_policy_id}:activate", self.activate_runtime_policy, methods=["POST"], response_model=RuntimePolicyResponse)

        r("/access-policies", self.create_access_policy, methods=["POST"], response_model=AccessPolicyResponse)
        r("/access-policies/{access_policy_id}/versions", self.create_access_policy_version, methods=["POST"], response_model=AccessPolicyVersionResponse)
        r("/access-policies/versions/{access_policy_version_id}:publish", self.publish_access_policy_version, methods=["POST"], response_model=AccessPolicyVersionResponse)

        r("/rate-limit-policies", self.create_rate_limit_policy, methods=["POST"], response_model=RateLimitPolicyResponse)
        r("/rate-limit-policies/{rate_limit_policy_id}/versions", self.create_rate_limit_policy_version, methods=["POST"], response_model=RateLimitPolicyVersionResponse)
        r("/rate-limit-policies/versions/{rate_limit_policy_version_id}:publish", self.publish_rate_limit_policy_version, methods=["POST"], response_model=RateLimitPolicyVersionResponse)

        r("/billing-policies", self.create_billing_policy, methods=["POST"], response_model=BillingPolicyResponse)
        r("/billing-policies/{billing_policy_id}/versions", self.create_billing_policy_version, methods=["POST"], response_model=BillingPolicyVersionResponse)
        r("/billing-policies/versions/{billing_policy_version_id}:publish", self.publish_billing_policy_version, methods=["POST"], response_model=BillingPolicyVersionResponse)
        r("/billing-policies/versions/{billing_policy_version_id}:activate", self.activate_billing_policy_version, methods=["POST"], response_model=BillingPolicyVersionResponse)

        r("/memory-policies", self.create_memory_policy, methods=["POST"], response_model=MemoryPolicyResponse)
        r("/memory-policies/{memory_policy_id}/versions", self.create_memory_policy_version, methods=["POST"], response_model=MemoryPolicyVersionResponse)
        r("/memory-policies/versions/{memory_policy_version_id}:publish", self.publish_memory_policy_version, methods=["POST"], response_model=MemoryPolicyVersionResponse)
        r("/memory-policies/versions/{memory_policy_version_id}:activate", self.activate_memory_policy_version, methods=["POST"], response_model=MemoryPolicyVersionResponse)

        r("/rag-policies", self.create_rag_policy, methods=["POST"], response_model=RagPolicyResponse)
        r("/rag-policies/{rag_policy_id}/versions", self.create_rag_policy_version, methods=["POST"], response_model=RagPolicyVersionResponse)
        r("/rag-policies/versions/{rag_policy_version_id}:publish", self.publish_rag_policy_version, methods=["POST"], response_model=RagPolicyVersionResponse)
        r("/rag-policies/versions/{rag_policy_version_id}:activate", self.activate_rag_policy_version, methods=["POST"], response_model=RagPolicyVersionResponse)

    @staticmethod
    def _ensure_scope(auth: AuthContext, scope: Scope) -> None:
        if scope.value not in auth.scopes:
            raise AuthorizationDeniedException(message="insufficient_scope")

    async def create_runtime_policy(
        self,
        payload: RuntimePolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RuntimePolicyResponse:
        self._ensure_scope(auth, Scope.RuntimePoliciesCreate)
        return await self.service.create_runtime_policy(
            tenant_id=auth.tenant_id,
            runtime_policy_create=payload,
            principal_id=auth.principal_id,
        )

    async def list_runtime_policies(
        self,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[RuntimePolicyResponse]:
        self._ensure_scope(auth, Scope.RuntimePoliciesList)
        return await self.service.list_runtime_policies(tenant_id=auth.tenant_id)

    async def activate_runtime_policy(
        self,
        runtime_policy_id: UUID,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RuntimePolicyResponse:
        self._ensure_scope(auth, Scope.RuntimePoliciesActivate)
        return await self.service.activate_runtime_policy(
            runtime_policy_id=runtime_policy_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def get_runtime_policy(
        self,
        runtime_policy_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RuntimePolicyResponse:
        self._ensure_scope(auth, Scope.RuntimePoliciesRead)
        return await self.service.get_runtime_policy(
            tenant_id=auth.tenant_id,
            runtime_policy_id=runtime_policy_id,
        )

    async def update_runtime_policy(
        self,
        runtime_policy_id: UUID,
        payload: RuntimePolicyUpdate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RuntimePolicyResponse:
        self._ensure_scope(auth, Scope.RuntimePoliciesUpdate)
        return await self.service.update_runtime_policy(
            tenant_id=auth.tenant_id,
            runtime_policy_id=runtime_policy_id,
            payload=payload,
        )

    async def create_access_policy(
        self,
        payload: AccessPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AccessPolicyResponse:
        self._ensure_scope(auth, Scope.AccessPoliciesCreate)
        return await self.service.create_access_policy(tenant_id=auth.tenant_id, payload=payload)

    async def create_access_policy_version(
        self,
        access_policy_id: UUID,
        payload: AccessPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AccessPolicyVersionResponse:
        self._ensure_scope(auth, Scope.AccessPolicyVersionsCreate)
        return await self.service.create_access_policy_version(
            access_policy_id=access_policy_id,
            payload=payload,
        )

    async def publish_access_policy_version(
        self,
        access_policy_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> AccessPolicyVersionResponse:
        self._ensure_scope(auth, Scope.AccessPolicyVersionsPublish)
        return await self.service.publish_access_policy_version(
            access_policy_version_id=access_policy_version_id
        )

    async def create_rate_limit_policy(
        self,
        payload: RateLimitPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RateLimitPolicyResponse:
        self._ensure_scope(auth, Scope.RateLimitPoliciesCreate)
        return await self.service.create_rate_limit_policy(tenant_id=auth.tenant_id, payload=payload)

    async def create_rate_limit_policy_version(
        self,
        rate_limit_policy_id: UUID,
        payload: RateLimitPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RateLimitPolicyVersionResponse:
        self._ensure_scope(auth, Scope.RateLimitPolicyVersionsCreate)
        return await self.service.create_rate_limit_policy_version(
            rate_limit_policy_id=rate_limit_policy_id,
            payload=payload,
        )

    async def publish_rate_limit_policy_version(
        self,
        rate_limit_policy_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RateLimitPolicyVersionResponse:
        self._ensure_scope(auth, Scope.RateLimitPolicyVersionsPublish)
        return await self.service.publish_rate_limit_policy_version(
            rate_limit_policy_version_id=rate_limit_policy_version_id
        )

    async def create_billing_policy(
        self,
        payload: BillingPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> BillingPolicyResponse:
        self._ensure_scope(auth, Scope.BillingPoliciesCreate)
        return await self.service.create_billing_policy(tenant_id=auth.tenant_id, payload=payload)

    async def create_billing_policy_version(
        self,
        billing_policy_id: UUID,
        payload: BillingPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> BillingPolicyVersionResponse:
        self._ensure_scope(auth, Scope.BillingPolicyVersionsCreate)
        return await self.service.create_billing_policy_version(
            billing_policy_id=billing_policy_id,
            payload=payload,
        )

    async def publish_billing_policy_version(
        self,
        billing_policy_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> BillingPolicyVersionResponse:
        self._ensure_scope(auth, Scope.BillingPolicyVersionsPublish)
        return await self.service.publish_billing_policy_version(
            billing_policy_version_id=billing_policy_version_id
        )

    async def activate_billing_policy_version(
        self,
        billing_policy_version_id: UUID,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> BillingPolicyVersionResponse:
        self._ensure_scope(auth, Scope.BillingPolicyVersionsActivate)
        return await self.service.activate_billing_policy_version(
            tenant_id=auth.tenant_id,
            billing_policy_version_id=billing_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def create_memory_policy(
        self,
        payload: MemoryPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> MemoryPolicyResponse:
        self._ensure_scope(auth, Scope.MemoryPoliciesCreate)
        return await self.service.create_memory_policy(tenant_id=auth.tenant_id, payload=payload)

    async def create_memory_policy_version(
        self,
        memory_policy_id: UUID,
        payload: MemoryPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> MemoryPolicyVersionResponse:
        self._ensure_scope(auth, Scope.MemoryPolicyVersionsCreate)
        return await self.service.create_memory_policy_version(
            memory_policy_id=memory_policy_id,
            payload=payload,
        )

    async def publish_memory_policy_version(
        self,
        memory_policy_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> MemoryPolicyVersionResponse:
        self._ensure_scope(auth, Scope.MemoryPolicyVersionsPublish)
        return await self.service.publish_memory_policy_version(
            memory_policy_version_id=memory_policy_version_id
        )

    async def activate_memory_policy_version(
        self,
        memory_policy_version_id: UUID,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> MemoryPolicyVersionResponse:
        self._ensure_scope(auth, Scope.MemoryPolicyVersionsActivate)
        return await self.service.activate_memory_policy_version(
            tenant_id=auth.tenant_id,
            memory_policy_version_id=memory_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )

    async def create_rag_policy(
        self,
        payload: RagPolicyCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagPolicyResponse:
        self._ensure_scope(auth, Scope.RagPoliciesCreate)
        return await self.service.create_rag_policy(tenant_id=auth.tenant_id, payload=payload)

    async def create_rag_policy_version(
        self,
        rag_policy_id: UUID,
        payload: RagPolicyVersionCreate,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagPolicyVersionResponse:
        self._ensure_scope(auth, Scope.RagPolicyVersionsCreate)
        return await self.service.create_rag_policy_version(
            rag_policy_id=rag_policy_id,
            payload=payload,
        )

    async def publish_rag_policy_version(
        self,
        rag_policy_version_id: UUID,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagPolicyVersionResponse:
        self._ensure_scope(auth, Scope.RagPolicyVersionsPublish)
        return await self.service.publish_rag_policy_version(
            rag_policy_version_id=rag_policy_version_id
        )

    async def activate_rag_policy_version(
        self,
        rag_policy_version_id: UUID,
        change: ChangeRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> RagPolicyVersionResponse:
        self._ensure_scope(auth, Scope.RagPolicyVersionsActivate)
        return await self.service.activate_rag_policy_version(
            tenant_id=auth.tenant_id,
            rag_policy_version_id=rag_policy_version_id,
            principal_id=auth.principal_id,
            change_request=change,
        )
