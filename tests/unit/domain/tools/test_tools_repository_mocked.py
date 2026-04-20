"""ToolsRepository paths with mocked session."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tools.repositories.tools_repository import ToolsRepository


def _tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


def _session_cm(session: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def tools_repo() -> ToolsRepository:
    return ToolsRepository(MagicMock(), tracer=_tracer(), cache_adapter=None)


@pytest.mark.asyncio
async def test_get_tool(tools_repo: ToolsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    tools_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await tools_repo.get_tool(uuid4()) is row


@pytest.mark.asyncio
async def test_get_tool_by_name(tools_repo: ToolsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    tools_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await tools_repo.get_tool_by_name("t1") is row


@pytest.mark.asyncio
async def test_list_tools(tools_repo: ToolsRepository) -> None:
    session = AsyncMock()
    t1 = MagicMock()
    res = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [t1]
    res.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=res)
    tools_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await tools_repo.list_tools(tenant_id=uuid4()) == [t1]


@pytest.mark.asyncio
async def test_get_max_version_patch(tools_repo: ToolsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    row.max_patch = 3
    res = MagicMock()
    res.one.return_value = row
    session.execute = AsyncMock(return_value=res)
    tools_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert (
        await tools_repo.get_max_version_patch(
            tool_id=uuid4(), tenant_id=uuid4()
        )
        == 3
    )


@pytest.mark.asyncio
async def test_get_tool_config(tools_repo: ToolsRepository) -> None:
    session = AsyncMock()
    row = MagicMock()
    res = MagicMock()
    res.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=res)
    tools_repo.db.get_session = MagicMock(return_value=_session_cm(session))
    assert await tools_repo.get_tool_config(uuid4()) is row


@pytest.mark.asyncio
async def test_list_published_tool_configs_empty_ids(
    tools_repo: ToolsRepository,
) -> None:
    out = await tools_repo.list_published_tool_configs_with_tools_by_config_ids(
        tenant_id=uuid4(),
        tool_config_ids=[],
    )
    assert out == []
