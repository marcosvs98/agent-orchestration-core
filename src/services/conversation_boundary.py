from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi.sse import ServerSentEvent

from domain.conversation.schemas.conversation import ConversationRequest
from domain.conversation.services.conversation_service import ConversationService
from domain.execution.schemas.execution import Channel
from domain.governance.schemas.scopes import Scope
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.services.rate_limit_service import RateLimitService
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    DomainValidationException,
)
from utils.auth import AuthContext


class ConversationBoundary:
    def __init__(
        self,
        conversation_service: ConversationService,
        access_policy_service: AccessPolicyService,
        rate_limit_service: RateLimitService,
    ) -> None:
        self.conversation_service = conversation_service
        self.access_policy_service = access_policy_service
        self.rate_limit_service = rate_limit_service

    async def send_message(
        self,
        *,
        auth: AuthContext,
        request: ConversationRequest,
        channel: Channel,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
        last_event_id: int | None,
        end_user_authorization: str | None = None,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        tenant_id = auth.tenant_id
        if tenant_id is None:
            raise AuthorizationDeniedException(message="tenant_id_required")
        is_human_principal = auth.principal_type in {"human", "user"}
        end_user_id = (request.user_id or "").strip()
        if not end_user_id:
            raise DomainValidationException(message="user_id_required")
        if is_human_principal and end_user_id != auth.principal_id:
            raise DomainValidationException(message="user_id_principal_mismatch")
        trusted_end_user_authorization = end_user_authorization
        await self.rate_limit_service.enforce(
            tenant_id=tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=Scope.ExecutionFlowRunCreate,
        )
        await self.access_policy_service.authorize(
            tenant_id=tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionFlowRunCreate),
        )
        return await self.conversation_service.execute_turn(
            tenant_id=tenant_id,
            canonical_principal_id=auth.principal_id,
            end_user_id=end_user_id,
            end_user_authorization=trusted_end_user_authorization,
            request=request,
            channel=channel,
            headers=headers,
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=trace_id,
            last_event_id=last_event_id,
        )
