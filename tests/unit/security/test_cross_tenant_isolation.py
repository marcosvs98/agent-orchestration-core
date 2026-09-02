"""Regression tests for the cross-tenant authorization holes in gap register §1.

Each test drives tenant A's credential at tenant B's resource and asserts the request is
refused before any mutation reaches the service layer.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.auth.controllers.auth_controller import AuthController
from domain.auth.schemas.auth import TenantTokenRequest, TenantTokenResponse
from domain.auth.services.auth_service import AuthService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.governance.controllers.governance_policies_controller import (
    GovernancePoliciesController,
)
from domain.governance.schemas.scopes import Scope
from domain.governance.services.governance_policies_service import (
    GovernancePoliciesService,
)
from domain.common.schemas.change import ChangeRequest
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    NotFoundServiceException,
)
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext

TENANT_A = uuid4()
TENANT_B = uuid4()


def _auth(tenant_id, scopes: set[str]) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        principal_type="machine",
        principal_id="principal-a",
        scopes=scopes,
        token_issuer="test-issuer",
        token_audience="test-audience",
        expires_at=9999999999,
    )


def _tracer() -> MagicMock:
    tracer = MagicMock(spec=RuntimeTracerPort)
    tracer.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return tracer


class TestTenantTokenMinting:
    @pytest.fixture
    def service(self) -> MagicMock:
        svc = MagicMock(spec=AuthService)
        svc.issue_tenant_token = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_tenant_scoped_caller_cannot_mint_for_another_tenant(self, service) -> None:
        controller = AuthController(service=service)
        auth = _auth(TENANT_A, {Scope.TenantsCreate.value})

        with pytest.raises(AuthorizationDeniedException, match="tenant_scope_mismatch"):
            await controller.issue_tenant_token(
                body=TenantTokenRequest(tenant_id=TENANT_B), auth=auth
            )

        service.issue_tenant_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_tenant_scoped_caller_may_mint_for_itself(self, service) -> None:
        controller = AuthController(service=service)
        auth = _auth(TENANT_A, {Scope.TenantsCreate.value})
        service.issue_tenant_token = AsyncMock(
            return_value=TenantTokenResponse(access_token="t", expires_in=60)
        )

        await controller.issue_tenant_token(body=TenantTokenRequest(tenant_id=TENANT_A), auth=auth)

        service.issue_tenant_token.assert_awaited_once_with(tenant_id=TENANT_A, auth=auth)

    @pytest.mark.asyncio
    async def test_minted_token_cannot_mint_again(self) -> None:
        tenants_repository = MagicMock()
        tenants_repository.get_tenant = AsyncMock(return_value=SimpleNamespace(tenant_id=TENANT_A))
        authoring_events = MagicMock()
        authoring_events.append_event = AsyncMock()
        service = AuthService(
            tenants_repository=tenants_repository,
            authoring_event_repository=authoring_events,
            inbound_service_key_repository=MagicMock(),
        )
        auth = _auth(None, {Scope.TenantsCreate.value, Scope.FlowsCreate.value})

        response = await service.issue_tenant_token(tenant_id=TENANT_A, auth=auth)

        from jose import jwt

        claims = jwt.get_unverified_claims(response.access_token)
        assert Scope.TenantsCreate.value not in claims["scopes"]
        assert Scope.FlowsCreate.value in claims["scopes"]
        assert claims["tenant_id"] == str(TENANT_A)


class TestExecutionBoundaryOwnership:
    def _boundary(self, owning_tenant_id) -> ExecutionBoundary:
        execution_service = MagicMock()
        execution_service.repository = MagicMock()
        execution_service.repository.get_flow_context = AsyncMock(
            return_value=(uuid4(), owning_tenant_id)
        )
        execution_service.resume_flow_run = AsyncMock()
        execution_service.list_execution_events = AsyncMock(return_value=[])
        tool_orchestrator = MagicMock()
        tool_orchestrator.execute_tool_run = AsyncMock()
        access_policy_service = MagicMock()
        access_policy_service.authorize = AsyncMock()
        rate_limit_service = MagicMock()
        rate_limit_service.enforce = AsyncMock()
        return ExecutionBoundary(
            execution_service=execution_service,
            agent_run_service=MagicMock(),
            tool_orchestrator=tool_orchestrator,
            access_policy_service=access_policy_service,
            rate_limit_service=rate_limit_service,
        )

    @pytest.mark.asyncio
    async def test_resume_rejects_foreign_flow_run(self) -> None:
        boundary = self._boundary(owning_tenant_id=TENANT_B)
        auth = _auth(TENANT_A, {Scope.ExecutionFlowRunResume.value})

        with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
            await boundary.resume_flow_run(
                auth=auth,
                flow_run_id=uuid4(),
                input_payload=None,
                channel="http",
                headers={},
                external_message_id=None,
                request_id=None,
                trace_id=None,
            )

        boundary.execution_service.resume_flow_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_tool_run_rejects_foreign_tool_run(self) -> None:
        boundary = self._boundary(owning_tenant_id=TENANT_B)
        node_run_id = uuid4()
        boundary.execution_service.repository.get_tool_run = AsyncMock(
            return_value=SimpleNamespace(node_run_id=node_run_id, agent_run_id=None)
        )
        boundary.execution_service.repository.get_node_run = AsyncMock(
            return_value=SimpleNamespace(flow_run_id=uuid4())
        )
        auth = _auth(TENANT_A, {Scope.ExecutionToolRunExecute.value})

        with pytest.raises(NotFoundServiceException, match="tool_run_not_found"):
            await boundary.execute_tool_run(auth=auth, tool_run_id=uuid4())

        boundary.tool_orchestrator.execute_tool_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_execution_events_scopes_query_to_caller_tenant(self) -> None:
        boundary = self._boundary(owning_tenant_id=TENANT_A)
        auth = _auth(TENANT_A, {Scope.ExecutionEventsList.value})

        await boundary.list_execution_events(auth=auth, flow_run_id=None, limit=10)

        boundary.execution_service.list_execution_events.assert_awaited_once_with(
            tenant_id=TENANT_A,
            flow_run_id=None,
            correlation_id=None,
            limit=10,
        )

    @pytest.mark.asyncio
    async def test_list_execution_events_rejects_foreign_flow_run(self) -> None:
        boundary = self._boundary(owning_tenant_id=TENANT_B)
        auth = _auth(TENANT_A, {Scope.ExecutionEventsList.value})

        with pytest.raises(NotFoundServiceException, match="flow_run_not_found"):
            await boundary.list_execution_events(auth=auth, flow_run_id=uuid4(), limit=10)

        boundary.execution_service.list_execution_events.assert_not_called()


class TestGovernanceVersionOwnership:
    def _service(self, owning_tenant_id) -> GovernancePoliciesService:
        foreign_policy = SimpleNamespace(tenant_id=owning_tenant_id)

        access_repository = MagicMock()
        access_repository.get_policy = AsyncMock(return_value=foreign_policy)
        access_repository.get_version = AsyncMock(
            return_value=SimpleNamespace(access_policy_id=uuid4())
        )
        access_repository.create_version = AsyncMock()
        access_repository.set_version_status = AsyncMock()

        rag_repository = MagicMock()
        rag_repository.get_policy = AsyncMock(return_value=foreign_policy)
        rag_repository.get_version = AsyncMock(return_value=SimpleNamespace(rag_policy_id=uuid4()))
        rag_repository.set_active_version = AsyncMock()

        runtime_repository = MagicMock()
        runtime_repository.get_policy = AsyncMock(return_value=foreign_policy)
        runtime_repository.activate_policy = AsyncMock()

        return GovernancePoliciesService(
            runtime_repository=runtime_repository,
            access_repository=access_repository,
            rate_limit_repository=MagicMock(),
            billing_repository=MagicMock(),
            memory_repository=MagicMock(),
            rag_repository=rag_repository,
        )

    @pytest.mark.asyncio
    async def test_publish_access_policy_version_rejects_foreign_policy(self) -> None:
        service = self._service(owning_tenant_id=TENANT_B)

        with pytest.raises(NotFoundServiceException, match="access_policy_version_not_found"):
            await service.publish_access_policy_version(
                tenant_id=TENANT_A, access_policy_version_id=uuid4()
            )

        service.access_repository.set_version_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_access_policy_version_rejects_foreign_policy(self) -> None:
        service = self._service(owning_tenant_id=TENANT_B)

        with pytest.raises(NotFoundServiceException, match="access_policy_not_found"):
            await service.create_access_policy_version(
                tenant_id=TENANT_A, access_policy_id=uuid4(), payload=MagicMock()
            )

        service.access_repository.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_runtime_policy_rejects_foreign_policy(self) -> None:
        service = self._service(owning_tenant_id=TENANT_B)

        with pytest.raises(NotFoundServiceException, match="runtime_policy_not_found"):
            await service.activate_runtime_policy(
                tenant_id=TENANT_A,
                runtime_policy_id=uuid4(),
                principal_id="p",
                change_request=ChangeRequest(change_type="UPDATE", justification="because"),
            )

        service.runtime_repository.activate_policy.assert_not_called()

    @pytest.mark.asyncio
    async def test_activate_rag_policy_version_rejects_foreign_version(self) -> None:
        service = self._service(owning_tenant_id=TENANT_B)

        with pytest.raises(NotFoundServiceException, match="rag_policy_version_not_found"):
            await service.activate_rag_policy_version(
                tenant_id=TENANT_A,
                rag_policy_version_id=uuid4(),
                principal_id="p",
                change_request=ChangeRequest(change_type="UPDATE", justification="because"),
            )

        service.rag_repository.set_active_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_controller_passes_caller_tenant_to_version_paths(self) -> None:
        service = MagicMock(spec=GovernancePoliciesService)
        service.publish_access_policy_version = AsyncMock()
        controller = GovernancePoliciesController(service=service)
        auth = _auth(TENANT_A, {Scope.AccessPolicyVersionsPublish.value})
        version_id = uuid4()

        await controller.publish_access_policy_version(
            access_policy_version_id=version_id, auth=auth
        )

        service.publish_access_policy_version.assert_awaited_once_with(
            tenant_id=TENANT_A,
            access_policy_version_id=version_id,
        )


class TestLLMAdminSurface:
    def test_admin_llm_router_requires_admin_credential(self) -> None:
        from domain.governance.controllers.llm_admin_controller import LLMAdminController
        from utils.auth import get_admin_auth

        controller = LLMAdminController(service=MagicMock())
        dependency_calls = [d.dependency for d in controller.router.dependencies]

        assert get_admin_auth in dependency_calls

    def test_admin_llm_routes_take_tenant_from_body_not_query(self) -> None:
        from domain.governance.controllers.llm_admin_controller import LLMAdminController

        controller = LLMAdminController(service=MagicMock())
        for route in controller.router.routes:
            query_params = [
                param.name
                for param in route.dependant.query_params  # type: ignore[attr-defined]
            ]
            assert "tenant_id" not in query_params
