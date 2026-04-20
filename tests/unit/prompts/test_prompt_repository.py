from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.prompts.repositories.prompt_repository import PromptRepository
from domain.prompts.schemas.prompt import NodePrompt, NodePromptCreate, NodeType


def _fake_tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


class TestPromptRepository:
    @pytest.mark.asyncio
    async def test_get_active_prompt_returns_none_when_not_found(self):
        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        db.get_session = MagicMock(return_value=cm)

        repo = PromptRepository(db, _fake_tracer())
        result = await repo.get_active_prompt(NodeType.ToolResolver.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_prompt_returns_prompt_when_found(self):
        prompt_id = uuid4()
        now = datetime.now(timezone.utc)
        model = MagicMock()
        model.to_dict.return_value = {
            "prompt_id": prompt_id,
            "node_type": NodeType.ToolResolver.value,
            "template_text": "Test prompt",
            "input_schema": None,
            "output_schema": None,
            "version": 1,
            "frozen_hash": "abc123",
            "is_active": True,
            "description": None,
            "created_by": "test_user",
            "created_at": now,
            "updated_at": now,
        }

        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=model))
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        db.get_session = MagicMock(return_value=cm)

        repo = PromptRepository(db, _fake_tracer())
        result = await repo.get_active_prompt(NodeType.ToolResolver.value)

        assert result is not None
        assert result.prompt_id == prompt_id
        assert result.node_type == NodeType.ToolResolver.value
        assert result.template_text == "Test prompt"
        assert result.version == 1
        assert result.frozen_hash == "abc123"

    @pytest.mark.asyncio
    async def test_create_prompt_creates_new_prompt(self):
        prompt_id = uuid4()
        now = datetime.now(timezone.utc)
        create = NodePromptCreate(
            node_type=NodeType.ToolResolver.value,
            template_text="New prompt",
            description="Test description",
            created_by="test_user",
        )

        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def refresh_side_effect(inst: object) -> None:
            setattr(inst, "prompt_id", prompt_id)
            setattr(inst, "created_at", now)
            setattr(inst, "updated_at", now)

        session.refresh = AsyncMock(side_effect=refresh_side_effect)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        db.get_session = MagicMock(return_value=cm)

        repo = PromptRepository(db, _fake_tracer())
        result = await repo.create_prompt(create, "hash123")

        assert result is not None
        assert result.prompt_id == prompt_id
        assert result.node_type == create.node_type
        assert result.template_text == create.template_text
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_deactivate_prompt_sets_is_active_false(self):
        db = MagicMock()
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        db.get_session = MagicMock(return_value=cm)

        repo = PromptRepository(db, _fake_tracer())
        await repo.deactivate_prompt(uuid4())

        session.execute.assert_called_once()
        session.commit.assert_called_once()
