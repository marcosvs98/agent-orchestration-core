from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.conversation.schemas.conversation import ConversationRequest
from domain.execution.schemas.execution import Channel
from domain.governance.schemas.scopes import Scope
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    DomainValidationException,
)
from services.conversation_boundary import ConversationBoundary
from utils.auth import AuthContext


@pytest.mark.asyncio
async def test_send_message_requires_tenant_id() -> None:
    boundary = ConversationBoundary(
        conversation_service=MagicMock(),
        access_policy_service=MagicMock(),
        rate_limit_service=MagicMock(),
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="hello",
    )
    auth = AuthContext(
        tenant_id=None,
        principal_type="human",
        principal_id="user-1",
        scopes=set(),
        token_issuer="test-issuer",
        token_audience="test-audience",
        expires_at=9999999999,
    )

    with pytest.raises(AuthorizationDeniedException, match="tenant_id_required"):
        await boundary.send_message(
            auth=auth,
            request=request,
            channel=Channel.HTTP,
            headers={},
            external_message_id=None,
            request_id="req-1",
            trace_id="trace-1",
            last_event_id=None,
        )


@pytest.mark.asyncio
async def test_send_message_rejects_user_id_mismatch() -> None:
    boundary = ConversationBoundary(
        conversation_service=MagicMock(),
        access_policy_service=MagicMock(),
        rate_limit_service=MagicMock(),
    )
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="forged-user",
        user_input="hello",
    )
    auth = AuthContext(
        tenant_id=uuid4(),
        principal_type="human",
        principal_id="user-1",
        scopes={Scope.ExecutionFlowRunCreate.value},
        token_issuer="test-issuer",
        token_audience="test-audience",
        expires_at=9999999999,
    )

    with pytest.raises(DomainValidationException, match="user_id_principal_mismatch"):
        await boundary.send_message(
            auth=auth,
            request=request,
            channel=Channel.HTTP,
            headers={},
            external_message_id=None,
            request_id="req-1",
            trace_id="trace-1",
            last_event_id=None,
        )


@pytest.mark.asyncio
async def test_send_message_delegates_to_conversation_service() -> None:
    conversation_service = MagicMock()
    rate_limit_service = MagicMock()
    rate_limit_service.enforce = AsyncMock()
    access_policy_service = MagicMock()
    access_policy_service.authorize = AsyncMock()

    async def _fake_execute_turn(**kwargs: object) -> object:
        del kwargs

        async def _gen() -> AsyncGenerator[MagicMock, None]:
            yield MagicMock()

        return _gen()

    conversation_service.execute_turn = AsyncMock(side_effect=_fake_execute_turn)
    boundary = ConversationBoundary(
        conversation_service=conversation_service,
        access_policy_service=access_policy_service,
        rate_limit_service=rate_limit_service,
    )
    tenant_id = uuid4()
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="user-1",
        user_input="hello",
    )
    auth = AuthContext(
        tenant_id=tenant_id,
        principal_type="human",
        principal_id="user-1",
        scopes={Scope.ExecutionFlowRunCreate.value},
        token_issuer="test-issuer",
        token_audience="test-audience",
        expires_at=9999999999,
    )

    stream = await boundary.send_message(
        auth=auth,
        request=request,
        channel=Channel.HTTP,
        headers={"x-test": "1"},
        external_message_id="ext-1",
        request_id="req-1",
        trace_id="trace-1",
        last_event_id=3,
        end_user_authorization="Bearer trusted-jwt",
    )

    rate_limit_service.enforce.assert_awaited_once()
    access_policy_service.authorize.assert_awaited_once()
    conversation_service.execute_turn.assert_awaited_once()
    kwargs = conversation_service.execute_turn.await_args.kwargs
    assert kwargs["canonical_principal_id"] == "user-1"
    assert kwargs["end_user_id"] == "user-1"
    assert kwargs["end_user_authorization"] == "Bearer trusted-jwt"
    assert stream is not None


@pytest.mark.asyncio
async def test_send_message_machine_principal_forwards_trusted_end_user_authorization() -> None:
    conversation_service = MagicMock()
    rate_limit_service = MagicMock()
    rate_limit_service.enforce = AsyncMock()
    access_policy_service = MagicMock()
    access_policy_service.authorize = AsyncMock()

    async def _fake_execute_turn(**kwargs: object) -> object:
        del kwargs

        async def _gen() -> AsyncGenerator[MagicMock, None]:
            yield MagicMock()

        return _gen()

    conversation_service.execute_turn = AsyncMock(side_effect=_fake_execute_turn)
    boundary = ConversationBoundary(
        conversation_service=conversation_service,
        access_policy_service=access_policy_service,
        rate_limit_service=rate_limit_service,
    )
    tenant_id = uuid4()
    request = ConversationRequest(
        agent_id=uuid4(),
        user_id="end-user-1",
        user_input="hello",
    )
    auth = AuthContext(
        tenant_id=tenant_id,
        principal_type="machine",
        principal_id="service-key-1",
        scopes={Scope.ExecutionFlowRunCreate.value},
        token_issuer="test-issuer",
        token_audience="test-audience",
        expires_at=9999999999,
    )

    stream = await boundary.send_message(
        auth=auth,
        request=request,
        channel=Channel.HTTP,
        headers={"x-test": "1"},
        external_message_id="ext-1",
        request_id="req-1",
        trace_id="trace-1",
        last_event_id=3,
        end_user_authorization="Bearer user-jwt",
    )

    kwargs = conversation_service.execute_turn.await_args.kwargs
    assert kwargs["canonical_principal_id"] == "service-key-1"
    assert kwargs["end_user_id"] == "end-user-1"
    assert kwargs["end_user_authorization"] == "Bearer user-jwt"
    assert stream is not None
