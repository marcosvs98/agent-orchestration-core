from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.conversation.schemas.conversation_read import InteractionReadRecord
from domain.conversation.services.conversation_read_service import (
    ConversationReadService,
)
from exceptions.service_exceptions import NotFoundServiceException


@pytest.mark.asyncio
async def test_get_end_user_detail_raises_when_user_missing() -> None:
    read_repo = AsyncMock()
    read_repo.get_end_user_id = AsyncMock(return_value=None)
    exec_repo = AsyncMock()
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=exec_repo
    )
    tenant_id = uuid4()
    with pytest.raises(NotFoundServiceException):
        await service.get_end_user_detail(tenant_id=tenant_id, user_id="u1")


@pytest.mark.asyncio
async def test_get_end_user_detail_merges_preferences_and_profile() -> None:
    tenant_id = uuid4()
    end_user_id = uuid4()
    read_repo = AsyncMock()
    read_repo.get_end_user_id = AsyncMock(return_value=end_user_id)
    exec_repo = AsyncMock()
    exec_repo.get_user_preferences = AsyncMock(return_value={"k": "v"})
    exec_repo.get_user_memory_profile = AsyncMock(return_value={"bio": "x"})
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=exec_repo
    )
    result = await service.get_end_user_detail(tenant_id=tenant_id, user_id="ext-1")
    assert result.end_user_id == end_user_id
    assert result.user_id == "ext-1"
    assert result.preferences == {"k": "v"}
    assert result.memory_profile == {"bio": "x"}


@pytest.mark.asyncio
async def test_list_interactions_by_session_delegates() -> None:
    tenant_id = uuid4()
    sid = uuid4()
    iid = uuid4()
    ts = datetime.now(timezone.utc)
    row = InteractionReadRecord(
        interaction_id=iid,
        session_id=sid,
        flow_run_id=None,
        result_node_run_id=None,
        channel="http",
        received_at=ts,
        external_message_id=None,
        request_id=None,
        trace_id=None,
        payload=None,
        output=None,
        headers=None,
    )
    read_repo = AsyncMock()
    read_repo.list_interactions_by_session = AsyncMock(return_value=([row], False))
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=AsyncMock()
    )
    out = await service.list_interactions(
        tenant_id=tenant_id,
        session_id=sid,
        user_id=None,
        limit=10,
        offset=0,
    )
    assert len(out.items) == 1
    assert out.items[0].interaction_id == iid
    assert out.items[0].user_input is None
    assert out.items[0].system_output is None
    assert out.has_next is False
    read_repo.list_interactions_by_session.assert_called_once()


@pytest.mark.asyncio
async def test_list_interactions_by_user_delegates() -> None:
    tenant_id = uuid4()
    read_repo = AsyncMock()
    read_repo.list_interactions_by_user = AsyncMock(return_value=([], True))
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=AsyncMock()
    )
    out = await service.list_interactions(
        tenant_id=tenant_id,
        session_id=None,
        user_id="u99",
        limit=5,
        offset=10,
    )
    assert out.items == []
    assert out.has_next is True
    assert out.offset == 10
    read_repo.list_interactions_by_user.assert_called_once_with(
        tenant_id=tenant_id,
        user_id="u99",
        limit=5,
        offset=10,
    )


@pytest.mark.asyncio
async def test_list_interactions_maps_user_input_and_system_output() -> None:
    tenant_id = uuid4()
    sid = uuid4()
    iid = uuid4()
    ts = datetime.now(timezone.utc)
    ts_done = datetime.now(timezone.utc)
    row = InteractionReadRecord(
        interaction_id=iid,
        session_id=sid,
        flow_run_id=None,
        result_node_run_id=None,
        channel="http",
        received_at=ts,
        completed_at=ts_done,
        external_message_id=None,
        request_id=None,
        trace_id="t1",
        payload={"input": {"user_input": "hello"}},
        output={"system_output": "hi there"},
        headers={"authorization": "secret"},
    )
    read_repo = AsyncMock()
    read_repo.list_interactions_by_session = AsyncMock(return_value=([row], False))
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=AsyncMock()
    )
    out = await service.list_interactions(
        tenant_id=tenant_id,
        session_id=sid,
        user_id=None,
        limit=10,
        offset=0,
    )
    assert out.items[0].user_input == "hello"
    assert out.items[0].system_output == "hi there"
    assert out.items[0].completed_at == ts_done
    assert not hasattr(out.items[0], "payload")


@pytest.mark.asyncio
async def test_list_sessions_and_end_users() -> None:
    tenant_id = uuid4()
    read_repo = AsyncMock()
    read_repo.list_sessions = AsyncMock(
        return_value=(
            [
                MagicMock(session_id=uuid4(), user_id="a"),
            ],
            False,
        )
    )
    read_repo.list_end_users = AsyncMock(
        return_value=(
            [
                MagicMock(end_user_id=uuid4(), user_id="b"),
            ],
            True,
        )
    )
    service = ConversationReadService(
        read_repository=read_repo, execution_repository=AsyncMock()
    )
    s = await service.list_sessions(
        tenant_id=tenant_id, user_id="a", limit=20, offset=0
    )
    assert len(s.items) == 1
    assert s.items[0].user_id == "a"
    e = await service.list_end_users(tenant_id=tenant_id, limit=20, offset=0)
    assert len(e.items) == 1
    assert e.has_next is True
