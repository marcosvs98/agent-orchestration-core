from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from domain.conversation.controllers.conversation_read_controller import (
    ConversationReadController,
)
from utils.auth import AuthContext


@pytest.fixture
def auth() -> AuthContext:
    return AuthContext(
        tenant_id=uuid4(),
        principal_type="human",
        principal_id="p1",
        scopes={"conversations:read"},
        token_issuer="test",
        token_audience="test",
        expires_at=9999999999,
    )


@pytest.fixture
def controller() -> ConversationReadController:
    svc = MagicMock()
    svc.list_interactions = AsyncMock()
    svc.list_sessions = AsyncMock()
    svc.list_end_users = AsyncMock()
    svc.get_end_user_detail = AsyncMock()
    return ConversationReadController(service=svc)


@pytest.mark.asyncio
async def test_list_interactions_422_when_neither_filter(
    controller: ConversationReadController, auth: AuthContext
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await controller.list_interactions(
            session_id=None,
            user_id=None,
            limit=50,
            offset=0,
            auth=auth,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_list_interactions_422_when_both_filters(
    controller: ConversationReadController, auth: AuthContext
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await controller.list_interactions(
            session_id=uuid4(),
            user_id="x",
            limit=50,
            offset=0,
            auth=auth,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_list_interactions_calls_service_with_session(
    controller: ConversationReadController, auth: AuthContext
) -> None:
    sid = uuid4()
    await controller.list_interactions(
        session_id=sid,
        user_id=None,
        limit=10,
        offset=2,
        auth=auth,
    )
    controller.service.list_interactions.assert_called_once_with(
        tenant_id=auth.tenant_id,
        session_id=sid,
        user_id=None,
        limit=10,
        offset=2,
    )
